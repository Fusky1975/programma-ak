# ak_engine

Modern Python reimplementation of **Adventurer-Kings (AK)**, a play-by-mail
strategy game engine originally written in Turbo Pascal (1987-2006). The
original source lives in `../Programma Pascal.zip`.

This is being rebuilt in phases, reconstructed from the game's rulebook
(`Regolamento AK.doc`, and `AKMAN.TXT`/`RULES.AK`/`ADDEND.AK`/`INFO.AK`
inside the original zip) where the source doesn't help, since the original
engine's main turn-processing program was never included in the source
archive (only compiled as `AK.EXE`/`AK.OVR`).

- **Phase 1**: domain model + parser for the player move-submission `.K1`
  file format.
- **Phase 2**: hex map model (`models/map.py`) and Move-action resolution
  (`turn/movement.py`), for *adjacent* target hexes only.
- **Phase 3**: Explore-action resolution (`turn/exploration.py`): the
  deterministic cumulative exploration-percentage formula, also now wired
  into `resolve_move()`'s partial-exploration side effect.
- **Phase 4**: Army Type Table (`models/army_type.py`, rulebook [6.3]) and
  Recruit-action cost/limit resolution (`turn/recruit.py`).
- **Phase 5**: battle math primitives (`turn/combat.py`): quality
  multipliers, battle-line/overflight strength halving, the defender
  bonus, the nemesis penalty, and a win-probability estimate.
- **Phase 6**: battle line-up (`turn/battle_line.py`): dealing units into
  battle-line columns, per-column strength totaling (line-depth halving +
  overflight-group stacking + outflank bonus), the Tactical-ability
  switch-chance formula, and per-column contest odds.
- **Phase 7**: who wins (`turn/battle_luck.py`, `turn/battle_resolution.py`):
  the two random luck events (column luck on front-line units, one
  whole-battle luck event favoring a random side) and `resolve_battle()`,
  which lines up both sides, applies luck, and rolls an actual winner per
  column and overall.
- **Phase 8**: the rest of the battle/combat rules [6.3], [7.1]-[7.8], as
  isolated, tested modules:
  - `turn/strength.py`: the full effective-strength pipeline (race/terrain
    bonuses, quality-level modifiers, multiplicative special factors),
    sourced from the rulebook's exact ordered "Summary of factors"
    ([6.3]) found on a closer re-read.
  - `models/map.py TERRAIN_LINE_LENGTH_RANGE` + `turn/battle_line.py
    roll_terrain_line_length_cap`: real terrain-based line-length ranges
    from the rulebook's Terrain Table ([1.6]), replacing the previously
    unresolvable `terrain_line_length_cap` gap.
  - `turn/battle_line.py maybe_switch_front_line`: executes the
    Tactical-ability switch (previously only a probability formula).
  - `turn/duel.py`: Supreme Commander selection and duel demoralization
    [7.1].
  - `turn/pursuit.py`: pursuit-attempt selection and one-on-one standstill
    resolution [7.3].
  - `turn/retreat.py`: retreat destination and disband/mercenary fallback
    [7.4].
  - `turn/aftermath.py`: post-battle quality-level changes [7.5].
  - `turn/contested_province.py`: the contested-province yes/no rules
    [7.6].
  - `turn/conquest.py`: movement-point cost of conquest and sea battles
    [7.7].
  - `turn/multiple_contingents.py`: grouping allied attackers into one
    battle [7.8].
- **Phase 9**: a persistent game-state model (`models/game_state.py`:
  `KingdomState`, `ArmyState`, `ProvinceState`, `GameState`) and
  `turn/battle_orchestrator.py fight_battle()`, which wires Phases 5-8
  together end-to-end: compute strength for every army at a province ->
  `resolve_battle()` -> quality changes (`aftermath`) -> retreat/disband
  the clean-swept loser (`retreat`) -> update province
  ownership/contested status. This is the first module that mutates a
  persistent state object instead of operating on caller-supplied
  snapshots.
- **Phase 10**: `turn/move_execution.py execute_move()` connects a Move
  order to everything before it: `resolve_move()` (adjacency + partial
  exploration) -> automatic battle trigger via `fight_battle()` if the
  target holds a non-allied army -> `turn/conquest.py`'s movement-point
  cost (now actually deducted from `ArmyState.movement_points`, a new
  field) -> relocating the mover's surviving armies only if the move
  actually succeeds. Also fixes a bug this wiring surfaced: `fight_battle`'s
  home-province check compared against an attacking army's `.location`,
  which is still its *origin* before a triggered battle resolves -- it now
  correctly compares against the battle's own province.
- **Phase 11**: closes the loop from a real parsed move file to actual
  execution. `turn/hex_numbering.py` decodes an LMOVE phase's raw target
  integer into a `HexCoord` -- **an empirical discovery, not a sourced
  rule**: nothing in the rulebook or source explains this encoding, so
  every consecutive pair of real LMOVE targets across all 10
  `AK3__T*.K1` files was decoded under several `(width, offset)`
  hypotheses and checked for hex-adjacency; row-major decoding with
  **width 10** matched 78-84% of 93 real move pairs, far above the ~1-2%
  expected by chance (see the module docstring for the full methodology).
  `turn/plan_dispatch.py` then dispatches a parsed `Leader`'s `ActionPlan`
  phases to `execute_move()` (via that decoder) and `resolve_explore()`;
  `run_leader_plan()` walks every phase of a real leader's plan and
  proved this works end-to-end against an actual `AK3__T1.K1` fixture
  (see `tests/test_plan_dispatch.py`'s real-file test).
- **Phase 12**: adds Recruit to `plan_dispatch.py`, closing the gap Phase
  11 flagged as "next". `models/army_type.py ARMY_TYPE_BY_ORDINAL`
  transcribes `CTBOTH.PAS`'s `army` enum ordinal order directly (a
  *sourced* mapping, not empirical this time) and `turn/recruit_decode.py`
  uses it to decode a Recruit `PlanPhase`: `obj` is the target leader id
  (`NO_LEADER_SENTINEL` = `CTBOTH.PAS`'s `noleader = 255`), and
  `extra[1:]` (up to the `-1` terminator) is a list of requested
  `ArmyType`s -- confirmed against every real Recruit phase in the
  `AK3__T*.K1` fixtures, all of which decode cleanly to known types (e.g.
  `[0, 1, 1, 10, -1]` -> 2x Bowmen + 1x Warg Riders). At this phase,
  `plan_dispatch.py` only priced each requested type via
  `resolve_recruit()` (limits + gold cost) without creating armies or
  debiting a treasury -- see Phase 15, which closed that gap.
- **Phase 13**: adds Disband/Leave/Pick_Up decoding. `turn/army_list_decode.py`
  decodes all three (they share one branch in `CTBOTH.PAS`/`DEF2.PAS`'s
  `Read_HPlan`): `extra[0]` is a target leader id (`NO_LEADER_SENTINEL`
  for "no specific leader" -- meaningful for LEAVE's "give them to
  another leader" per rulebook [3.8]; present but unconfirmed for
  Disband/Pick_Up), and `extra[1:]` is either a specific army-id list or
  a lone `255`, read as an "all armies" flag matching "(LE)ave
  All"/"(DI)sband All"/"(PI)ck Up All". Confirmed against every real
  LEAVE phase across all 10 `AK3__T*.K1` files; only one real DISBAND
  example exists in the sample data and **zero** PICK_UP examples, so
  those two ride on the shared Pascal code path, not independent
  confirmation the way LEAVE's is. This phase was decode-only.
- **Phase 14**: the leader-army command model. `models/game_state.py`
  adds `LeaderState` (a persistent leader's kingdom/name/location --
  distinct from Phase 1's parsed `models.kingdom.Leader`, which carries
  an `ActionPlan` and shares only the `leader_id`) and `ArmyState
  .commanded_by` (which leader currently leads an army, `None` = unled/
  garrison). This unlocks real execution for two of Phase 13's
  decode-only actions:
  - **LEAVE** now actually transfers `commanded_by` to the requested
    leader (or clears it, for the garrison) and, per rulebook [3.8] ("If
    you Leave an army in an ally's province, the army then belongs to
    the ally"), reassigns `kingdom_id` too when the province is owned by
    an ally.
  - **PICK_UP** now attaches co-located armies (or, for "Pick Up All",
    every *unled* co-located army -- rulebook: "(PI)ck Up All UNLED
    armies... with Garrison Commander") to the acting leader.
  - **DISBAND still doesn't execute** -- releasing an army "into
    mercenary status" needs a way to represent an unowned army (nullable
    `ArmyState.kingdom_id` or a mercenary pool), which is a separate,
    still-open gap the command model alone doesn't close.
  `turn/move_execution.py execute_move()` also gained `leader_id` support:
  a character can now move *without* any army (rulebook [3.1]: combat
  only triggers "If the character has an army with him", so a lone
  leader walking into an enemy-held province doesn't fight), and
  `turn/plan_dispatch.py` now derives `army_ids` from
  `state.armies_commanded_by(leader_id)` by default instead of always
  requiring an explicit list -- closing the "which armies does a Move
  order pull in" gap from Phase 10/11. Every dispatch call requires an
  explicit `leader_id` now (a signature change from Phase 11-13).
- **Phase 15**: the kingdom treasury, and RECRUIT now actually
  executes instead of only pricing. Before writing this,
  `models/army_type.py ARMY_TABLE`'s 19 `pay` values were re-verified
  line by line against the rulebook's Army Type Table [6.3] (all
  correct), and a red herring in `CTBOTH.PAS` was chased down and ruled
  out: an `at_cost`/`atdesig` array that looks army-cost-related at a
  glance is actually indexed by an unrelated `retainer` enum (personal
  companions for character encounters -- Heralds, Armorers, Entertainers,
  etc., a different subsystem, confirmed via the `retainer` type
  declaration around `CTBOTH.PAS` line 1388) -- so `ARMY_TABLE.pay`
  remains the correct and only cost source. (Also spotted, but out of
  scope here: a per-ordinal nemesis table, `atnem1`/`atnemf`, that could
  be a useful future cross-check against `models/army_type.py NEMESIS`.)
  `turn/recruit_execution.py execute_recruit()` prices each requested
  type (reusing `resolve_recruit()`), debits `KingdomState.treasury`
  (crediting an ally's treasury too, "the recruiter pays 1 gold to his
  ally for each recruited army", rulebook [3.4]), and creates a new
  `ArmyState` per successfully recruited unit -- at `Average` quality
  (rulebook: "an army is levied from among the populace"; hiring an
  existing higher-quality mercenary instead wasn't modeled yet at this
  phase -- see Phase 16) with 0 movement points (a conservative default;
  the rulebook doesn't say whether a freshly recruited army can act the
  same phase). The per-type per-turn recruit limit is now enforced *across*
  multiple Recruit orders in the same province via the new
  `ProvinceState.recruited_this_turn` counter, not just within a single
  order. Requesting more of a type than the limit allows or the treasury
  can afford recruits as many as possible and reports the rest as
  blocked -- a documented choice, not a sourced rule (see
  `turn/recruit_execution.py`'s docstring).
  Every other `ActionCode` still raises `UnsupportedActionError` -- see
  "Not yet implemented" below. Report generation is still a later phase.
- **Phase 16 (current)**: the mercenary pool, closing the two gaps Phase
  15 flagged. `models/game_state.py ArmyState.kingdom_id` is now nullable
  -- `None` means an unowned mercenary army (rulebook [3.6]: Disband
  "releases the army(s) into mercenary status... will wander around as
  unemployed mercenaries until hired"), and a new `GameState
  .mercenaries_at()` helper finds them by location. `is_allied()` treats
  `None` as allied with nobody (two masterless bands aren't each other's
  allies just because both are ownerless), which required an audit of
  every existing `is_allied()`-based defender/occupancy check so a
  mercenary sitting in a province wouldn't be swept in as an automatic
  battle participant or read as "enemy-occupied" for a peaceful Move --
  fixed in both `turn/battle_orchestrator.py fight_battle()`'s defender
  filter and `turn/move_execution.py execute_move()`'s occupancy check
  (both now also require `kingdom_id is not None`), with regression tests
  covering exactly this case.
  - **DISBAND now actually executes**: `plan_dispatch._dispatch_disband`
    clears the targeted armies' `kingdom_id` and `commanded_by`. Unlike
    Pick_Up, co-location with the acting leader is **not** enforced --
    the rulebook grants Kings a broader disband authority than Heroes
    (who need to be with the army), and `LeaderState` doesn't yet
    distinguish the two, so this is a documented simplification rather
    than a guess at which restriction applies.
  - **A forced-mercenary defender from `_retreat_or_disband`** (battle
    orchestrator, existing since Phase 8/9) now actually becomes a real
    mercenary: it already got `unhireable_this_turn = True`, but its
    `kingdom_id`/`commanded_by` were left pointing at the loser -- now
    both are cleared too, so it's genuinely ownerless, not just flagged.
  - **Recruit hires an existing mercenary instead of levying fresh**
    (rulebook [3.4]: "if there is an Average or higher quality mercenary
    army of that type in the province, then the mercenaries are hired"):
    `execute_recruit()` checks `mercenaries_at()` for a co-located,
    matching-type, `quality >= Average`, currently-hireable army before
    creating a new one; if found, it's reassigned in place (preserving
    its existing, possibly higher, quality) instead of a fresh `Average`
    army being created. Costs the same as levying and counts against the
    same per-province `recruited_this_turn` limit -- the rulebook
    doesn't distinguish hiring from levying on price or limit, only on
    where the army comes from. Reported via the new
    `RecruitedUnit.hired: bool` field.
- **Phase 17 (current)**: Hire/Fire Hero (rulebook [3.5], [3.7]) --
  a different concept from Recruit's mercenary-*army* hiring: Hire/Fire
  operate on independent *characters* joining or leaving a kingdom's
  service as a leader. `models/game_state.py LeaderState.kingdom_id` is
  now nullable, same convention as Phase 16's `ArmyState.kingdom_id`:
  `None` means an independent Hero. `turn/hire_fire_decode.py` decodes
  both actions from `HostAK/TP/DEF2.PAS`'s `R_HPlan`/`W_HPlan`: Hire's
  `obj`/`extra[0]` is the target Hero id and gold offer (rulebook: "1-4
  gold"; validated exactly against all 10 real HIRE phases in the sample
  `AK3__T*.K1` files); Fire only has `obj` (the Hero id) -- confirmed
  from the Pascal source that Fire has no `CASE` branch in
  `R_HPlan`/`W_HPlan` at all (no extra data), though **zero real FIRE
  phases exist in the sample data** to independently verify this, unlike
  every other decoded action in this project.
  `plan_dispatch._dispatch_hire`/`_dispatch_fire` execute against
  `GameState`: Hire requires the target Hero to be independent and
  co-located with the acting leader, then debits the gold offer from the
  kingdom's treasury and assigns `kingdom_id`; Fire releases a Hero back
  to `kingdom_id = None`. ~~Co-location isn't enforced (same Disband-style
  King-vs-Hero simplification, `LeaderState` still has no King/Hero
  distinction)~~ **fixed in Phase 40**, see below. Several rulebook
  nuances are explicitly not modeled here (no data/formula exists for
  them, same situation as other entries in the TODO section below): a
  Hero's own "required pay" (which may be lower than the offer and
  depends on unmodeled per-Hero temper/race/alignment compatibility --
  **Phase 161 confirmed no Pascal source for this formula survives at
  all, and Phase 162 designs and implements one anyway** from the
  player's manual text plus a real hard data point, see that phase's
  own note below -- `_dispatch_hire` now charges the computed required
  pay, not the raw offer), recurring per-gameturn pay (only the initial
  charge is modeled, once -- still no sourced formula for the recurring
  case).
  ~~"Can't Hire a Hero who rules his own province" (no King flag to
  check against)~~ **also fixed in Phase 40**.
  **A real, confirmed parser bug was found while researching this
  phase** (fixed in Phase 18, see below): a Hire (or Charm/Resurrection
  Cast) phase's own nested plan for the newly-joined character was being
  silently discarded by `parser/k1_moves.py`.
- **Phase 18 (current)**: fixes that nested-plan parser bug.
  `parser/k1_moves.py`'s leader-block parser is now bounded
  recursive-descent instead of one flat token loop: each `AP: <start>
  <end>` segment reads *exactly* the phases `P<start>` through `P<end>`,
  in that order (`range(plan_start, plan_end + 1)`, a mismatch is now a
  real `K1ParseError` instead of silently accepting whatever keyword came
  next) -- and per `HostAK/TP/DEF2.PAS`'s "`IF m < 4 THEN
  R_HPLan(...)`", if a phase at position `P0`-`P3` (never `P4`) is
  immediately followed by another `AP:` token, that's recursively parsed
  as a **nested plan** and attached to `PlanPhase.nested_plan`, instead
  of being appended as a bogus sibling `PlanSegment` that clobbers the
  outer leader's own same-labeled phases later in the stream. This same
  `P0`-vs-`P4` position is exactly what disambiguates "nested plan" from
  a genuine new top-level segment for the same leader (only possible
  right after a `P4`). Verified against all 10 real `AK3__T*.K1` files:
  every leader now parses to **exactly one** top-level segment with zero
  leftover tokens -- the previously-claimed "multi-segment leaders"
  (`AK3__T3.K1`, `AK3__T10.K1`, asserted by a Phase 1 test) turned out to
  be entirely an artifact of this bug; that test was corrected
  accordingly. New tests cover the flagship real-data case
  (`AK3__T2.K1` leader 18's Hire of hero 32, whose own P2-P4 moves are
  now correctly recovered instead of overwritten) and a real 3-level-deep
  nesting (`AK3__T9.K1` leader 72: Cast embeds Hire embeds another nested
  plan). `models/plan.py ActionPlan.leader_id` is now nullable, since a
  Cast-triggered nested plan's owning character id can't be recovered
  (this project doesn't decode spell ids); a Hire-triggered one always
  has a real id (Hire's own `obj`).
- **Phase 19 (current)**: Search Feature decoding (rulebook [3.3]) --
  structurally unlike Explore ([3.2]): Explore is an untargeted,
  deterministic percentage roll over the mover's own province; Search
  targets one *already-known* feature by number (possibly in a province
  the searcher doesn't own, or hasn't Explored, if a rumor gave up its
  number) and immediately triggers a personal Encounter against that
  feature's guardian monster (rulebook [5.0]), resolved via a
  player-supplied Encounter Plan -- an ordered list of combat tactics.
  `models/enums.py` gains `Maneuver` (transcribed from `CTBOTH.PAS`'s
  `maneuver` enum: Cast, Use_MI, Squeeze, Talk, Say, Give, Fulfill,
  Steal, Shoot, Melee, Flee, Beg, None, Scout). `turn/search_decode.py`
  decodes `obj` as the target feature id and the rest of `extra` as a
  `-1`-terminated tactic list (`HostAK/TP/DEF2.PAS`'s `R_HPlan`'s
  `R_List(..., Tac_Bytes, ...)` call), pairing a sub-object (spell/item
  id) onto a tactic only for Cast/Use_MI/Give, matching `W_List`'s
  `Tac_Bytes` mode exactly. Validated against all 12 real Search phases
  across 5 of the 10 sample `AK3__T*.K1` files: every one decodes to a
  clean, fully-consumed tactic list with no leftover tokens, and
  `extra[0]` ("tl" in the Pascal source) is `0` in every real example --
  kept as an unconfirmed raw field, same convention as Recruit's own
  always-`0` `extra[0]`. **Decode-only**, same status Recruit had before
  Phase 15: resolving what a Search actually *does* needs a personal,
  non-army Encounter/combat resolver this project doesn't have (distinct
  from `turn/combat.py`'s army battle math), plus the same stochastic
  treasure/monster-content generation already flagged as out of scope
  for Explore.
- **Phase 20 (current)**: Trade decoding -- the project's
  least-confirmed decode module so far. `ActionCode.TRADE` (`CTBOTH.PAS`
  ordinal 14) turns out to be the Pascal engine's internal name for the
  rulebook's **Give order** ([3.18]/[5.7]): the enum member is named
  `Trade`, but its abbreviation (`'GI'`) and turn-report message
  (`_LTrade: '< gave the \ to [.'`) both match "Give" exactly -- there's
  no separate `Give` enum member at all, and the "Trade" name most
  likely comes from Give's optional reciprocal-exchange variant ("the
  gift will be made only if the recipient Gives you a specified magic
  item in the same phase"). `turn/trade_decode.py` deliberately stays
  **raw**: `TradeRequest(obj, extra)` with no interpreted field names,
  because nothing here can be confirmed the way every earlier decode
  module's fields could be:
  - The rulebook's own text warns that `obj` can mean *either* a magic
    item id *or* a gold amount ("Be careful that you don't 'Give' an
    amount of gold that equals a magic item I.D. number") -- an
    acknowledged overload with no discriminator found anywhere in the
    available source.
  - `HostAK/TP/DEF2.PAS` confirms Trade reads one extra numeric field
    (`n1`) beyond the standard `obj`/`extra[0]` pair, but with **no
    comment naming what it means** (unlike Hire's clearly-labeled gold
    offer).
  - **Zero real Trade phases exist in any of the 10 sample
    `AK3__T*.K1` files** -- no empirical cross-check available, the
    situation Fire (Phase 17) was already in, except Fire at least had
    unambiguous Pascal-confirmed field semantics (no extra data at all)
    to fall back on.
  - **The actual turn-execution engine isn't present in the available
    Pascal source tree** -- only plan read/write/report-text code exists
    here, so even a Pascal-level (not just real-data) confirmation of
    the field mapping is unavailable.
  Given all of this, no field-position guess (e.g. "`extra[0]` is the
  recipient id") is asserted as fact anywhere in this module or its
  tests -- see `turn/trade_decode.py`'s docstring for the full reasoning.
  **Separately investigated and confirmed out of scope**: the user
  recalled a "Treat" diplomacy order for exchanging Sage discoveries
  between Allied kingdoms -- confirmed real (rulebook [8.2] Treating,
  [8.4] Scientific Treaties), but it is a **Kingdom-level** turnsheet
  order ("The Kingdom will Treat with (list King numbers)",
  `RUMORS.PAS`), structurally unrelated to `Trade`/Give and to the
  per-leader `PlanPhase`/`ActionCode` system entirely -- not a decode
  target for this module. It also doesn't appear anywhere in the 10
  sample `AK3__T*.K1` files (confirmed via a direct text search), so
  there's no real data to build against yet either. Parsing it would
  need extending `models/kingdom.py`'s `Kingdom`/`KingdomMoveHeader`
  model and `parser/k1_moves.py` for a new turnsheet field this project
  doesn't read at all today -- a distinct future task, not attempted
  here.
- **Phase 21 (current)**: Practice Ability decoding (rulebook [3.13]),
  plus a resolved long-standing unknown. `obj` maps directly onto the
  existing `Ability` enum (`turn/practice_decode.py`); `extra` carries no
  meaning for Practice at all (`DEF2.PAS`'s `R_HPlan`/`W_HPlan` has no
  `CASE` branch for it, unlike Search/Trade/Hire/Recruit) -- confirmed by
  real data: all 189 real Practice phases across the 10 sample
  `AK3__T*.K1` files have `extra == [0]`.
  **`models/kingdom.py SkillTable`'s pair is now resolved**:
  `(current_skill_level, current_aptitude_level)`, each 0-9. Confirmed
  three ways -- `CTME.PAS`'s `power` enum tracks `UpSkill`/`UpApt` as
  independent quantities; the King-creation formula (starting aptitude =
  skill+2, capped at 5, with race/alignment overrides) matches; and every
  one of `AK3__T1.K1`'s 15 real pairs matches that formula exactly,
  including both override cases (an Undead King's `WHITE = (0, 0)`,
  `NECROMANCY = (3, 5)`). The 31st trailing skill-line value stays
  unconfirmed (constant `3` across all 10 sample turns -- plausibly a
  race ordinal, not asserted since only one Kingdom's data is available).
  **Decode-only**: resolving what Practice actually does needs a
  per-leader skill/aptitude table in `GameState` (the move file only
  exposes the *King's* pairs -- 74% of real Practice instances belong to
  Heroes, who have none), a province-level view of every co-located
  character's same-phase action (rulebook [3.13]'s core mechanic --
  "2 or more characters... Practice the same ability in a phase" -- is
  inherently multi-character), and a dice-roll procedure not present in
  the available Pascal source (only the rulebook's percentages and
  `CTME.PAS`'s `apt_rise` aptitude-rise table are available). Also
  flagged for a future execution phase: Practicing **Tactical**
  ([6.1]) doesn't raise personal skill at all -- it rolls army
  quality-tier upgrades instead; Practicing **Sage** ([4.31]) rolls an
  independent ~5%/level "device discovery" chance alongside the normal
  skill roll.
- **Phase 22 (current)**: Wait, No_Action, and Move_Abort dispatch as
  bare no-ops -- no decode module, since an exhaustive grep of every
  ``lactions[...]`` site across the entire available Pascal source (all
  14 ``.PAS`` files) confirms none of the three has a ``CASE`` branch in
  `DEF2.PAS`'s `R_HPlan`/`W_HPlan`, so there's no extra payload beyond
  the generic `(action, obj, extra)` triple, and none has a single real
  example in the 10 sample `AK3__T*.K1` files either. None is documented
  as a player-issuable order in the rulebook (zero mentions anywhere).
  Wait and No_Action, however, are confirmed **engine-internal** values:
  `REPORTS.PAS Set_Defend` auto-fills a missed-turn-deadline king's
  leaders with Defend (phase 0) then Wait (phases 1-4); `DEF2.PAS
  Clear_M` initializes/pads every phase slot outside a plan's
  `planstart..planend` range to No_Action. Move_Abort is the most
  speculative of the three: declared in the `action` enum purely for
  abbreviation-table symmetry (`'MA'`), but never assigned to or
  compared against anywhere else in the entire available source --
  effectively vestigial as far as this project's source access goes.
  `plan_dispatch.py` gains a small `NoOpResult(action: ActionCode)`
  dataclass shared by all three.
- **Phase 23 (current)**: Cast Spell decoding (rulebook [3.10]), the
  second-most-common real action (108/10 sample files, after LMove).
  `models/enums.py` gains `Spell`, transcribed exactly from
  `CTBOTH.PAS`'s 56-member `spell` enum: the 25 documented base spells
  ([4.21]-[4.25], five per Magical `Ability`, packed as four
  "first-four-spells" blocks then one "fifth-spell" block, not five
  contiguous per-ability blocks), 10 undocumented "secret" spells
  (25-34, gated behind a special ability granted at skill 5+ --
  `CTBOTH.PAS`'s `spdex` lookup table), a `NOSPELL` sentinel (35), and
  20 unused/reserved placeholder ordinals not modeled. `obj` maps
  directly to `Spell`; `extra[0]` is the spell's target, whose meaning
  (character id / province id / unused) depends on which spell it is --
  `turn/cast_decode.py` exposes `CHARACTER_TARGET_SPELLS`/
  `PROVINCE_TARGET_SPELLS`/`NO_TARGET_SPELLS` lookup sets so callers
  don't have to hardcode this themselves, mirroring
  `search_decode.py`'s tactic-sub-object pattern. **Illusory Terrain**
  is the one spell with an extra field beyond the standard triple --
  its selected fake `Terrain` lands at `extra[1]`.
  Validated against all 108 real Cast phases across the 10 sample
  `AK3__T*.K1` files: 12 distinct spell ids appear, and -- independent
  confirmation the decode is right, not just plausible -- **every single
  one is a documented Action spell**, never one of the 10
  Personal-Combat-only spells, exactly matching rulebook [3.10]'s "must
  be an Action Spell, not a personal-combat spell" restriction. Skeletal
  Army's `extra[0]` is `0` in all 29 real examples, matching its
  documented "no target" case exclusively; both real Illusory Terrain
  casts have `extra == [target, 3]`, confirming `Terrain.FOREST`.
  **Also resolves part of a previously-flagged gap**: Charm and
  Resurrection are the two spells whose Cast phase embeds a nested plan
  (same mechanism as Hire, `DEF2.PAS Read_More`'s `Charm, Resurrection:
  Read_HPlan`) -- `parser/k1_moves.py`'s `_maybe_parse_nested_plan` now
  infers the nested character's real id from the spell's own target
  (`extra[0]`) for these two specifically, instead of always leaving
  `ActionPlan.leader_id` `None` for any Cast-triggered nesting. Verified
  against the real `AK3__T9.K1`/`AK3__T10.K1` nested-Charm/Resurrection
  examples already covered by Phase 18's tests (now asserting real ids
  instead of `None`).
  **Deliberately not modeled**: the Trade-\>Cast rewrite for secret
  spells 25-34 (`DEF2.PAS`'s `Trade` branch can reclassify a
  self-targeted Give into a Cast if the caster has the matching special
  ability) -- confirmed to exist in the Pascal source but zero real
  examples anywhere, and it belongs to `trade_decode.py` if ever built,
  not this module. **Decode-only** otherwise, same status as
  Search/Trade/Practice: resolving what a successful Cast actually does
  needs game-state mutation logic not present anywhere in the available
  Pascal source.
- **Phase 24 (current)**: Use Magic Item decoding (rulebook [3.11]).
  Structurally distinct from Cast in one key way: Use_MI's `obj` is a
  **global item-instance id** (an index into three parallel Pascal
  arrays -- `treaslist`/`trowner`/`trcharges` -- tracking every physical
  magic item in the game), not a self-describing type ordinal the way
  Cast's `obj` directly is a `Spell`. `turn/use_mi_decode.py` therefore
  cannot resolve "what item is this" from the move file alone -- doing
  so needs that specific game's item-creation history, and the only
  Pascal source for creating an item instance (`RUMORS.PAS`'s `Add_Tr`)
  has just one caller in the available source (a narrow Valhalla-visitor
  special case), not a general loot/world-gen pipeline. `UseMIRequest`
  stays honestly raw: `item_instance_id`, a generic `target`, and (only
  if a second `extra` element is present) a `terrain`, mirroring Cast's
  `Illus_Terrain` sub-read since the same `Read_More` mechanism fires
  when the resolved item type is a spell-casting wand.
  The underlying `treasure` type enum was fully reconstructed for
  context (`CTBOTH.PAS` lines 605-645, cross-referenced against the
  obfuscated identifiers' real names/mechanics in
  `HostAK/TP/PROSE/TREASURE.X2`/`TREASAB.X2`): 113 ordinals across seven
  functional groups, only two of which -- 20 spell-casting wands and 15
  one-shot skill-boosting books, 35 of 113 -- are legitimate `Use_MI`
  targets at all; the rest (ability-boosting items, named weapons,
  amulets, monster-command items, plus non-item bookkeeping/quest-
  tracking/scenario-specific/unused ordinals) "operate automatically"
  per rulebook [5.9] and are never invoked by this action. Not
  transcribed into `models/item.py` this phase -- would need a careful
  direct read of the prose files for all 113 entries, not attempted
  here to avoid asserting names beyond what's been anchor-verified.
  **Zero real Use_MI phases exist in any of the 10 sample
  `AK3__T*.K1` files** (confirmed via this project's own parser, not
  just a text search) -- same situation as Fire and Trade.
- **Phase 25 (current)**: Challenge and Pursue decoding, sharing one
  module (`turn/challenge_pursue_decode.py`) since they're wire-
  identical to Search -- `DEF2.PAS`'s `Search,Challenge,Pursue:
  W_List(...,Tac_Bytes)` handles all three together, same `-1`-
  terminated tactic-list format already decoded for Search, reused here
  via `search_decode.py`'s `SearchTactic` rather than a near-duplicate
  type. The one real difference: `obj` is a target **character** id for
  both, not a feature id -- confirmed by the rulebook, the official
  move-sheet example (`(EN)_88_____` / `(_Lancelot__)`), and Pascal
  itself (`R_List` is called with `sfeat = -(lobjects[m]+1)`, always
  negative, deliberately routing around `R_List`'s Search-only
  feature-id special case). `ActionCode.CHALLENGE` turns out to be
  another Pascal-vs-rulebook naming mismatch (like Trade/Give): its
  `actab` abbreviation is `'EN'`, matching the rulebook's **Encounter
  Character (EN)** order ([3.12]), not literally "Challenge."
  `ActionCode.PURSUE` matches its own rulebook order directly ([3.16]):
  a player-issued "chase this character across the map" order (success
  via the Spy Table [4.33]: base chance by Spy level, `x2` if the target
  leads an army, `/` distance in provinces, `100%` if same Kingdom) --
  confirmed **entirely unrelated** to `turn/pursuit.py`'s separate,
  already-implemented automatic post-battle retreat-chasing mechanic
  ([7.3]); no Pascal-source overlap between the two, and this phase
  doesn't touch `turn/pursuit.py`. A documented nuance left unmodeled:
  targeting one's own character id turns Pursue into a standing
  "Patrol" order. **Zero real Challenge or Pursue phases exist in any of
  the 10 sample files** (double-confirmed: a raw-text scan and a full
  parser walk including nested plans both agree) -- weaker evidence than
  Search's own 12 real examples, same situation as Fire/Trade/Use_MI.
- **Phase 26 (current)**: ASpy and Defend decoding
  (`turn/aspy_defend_decode.py`), rulebook [3.14] Spy Province and
  [3.15] Defend. Both are bare `(action, obj, extra)` triples in
  `DEF2.PAS` (no dedicated `CASE` branch), which would normally put them
  in the same bucket as Wait/No_Action/Move_Abort -- except `obj` is
  confirmed to be a real, engine-consulted province reference rather
  than dead data: `RUMORS.PAS`'s `Set_Intel` reads `lobjects[_rphase]`
  for ASpy against the province currently being processed for
  intelligence purposes; `REPORTS.PAS`'s `Set_Defend` (the
  missed-turn-deadline auto-fill, first found while researching Phase
  22's Wait/No_Action) explicitly *writes* `lobjects[0]:=
  lx[l2]*XMULT+ly[l2]` -- the general's own province, confirming a real
  province-coordinate target. Neither `ActionCode` name has a
  Trade/Challenge-style mismatch: `actab[ASpy] = 'SP'` and
  `actab[Defend] = 'DE'` both match their own rulebook abbreviations
  directly. `target_province` is kept as a **raw, unconverted int**,
  deliberately not run through `turn/hex_numbering.py`'s LMOVE decoder
  -- nothing in the available source confirms whether a player-typed
  province number for these two actions shares that same (itself only
  empirically inferred) numbering space, or maps onto `Set_Defend`'s
  internal `x*XMULT+y` arithmetic instead; stacking one unconfirmed
  mapping on another would overstate this project's actual certainty.
  A rule found only in the **Italian** rulebook, not `RULES.AK`: a
  Defend order always resolves last in its phase (the general must be
  able to react to every other action first) -- noted for whenever
  phase-ordering/initiative gets modeled, not implemented here.
  **Zero real ASpy or Defend phases exist in any of the 10 sample
  files** (re-verified fresh via the real parser) -- same situation as
  Fire, Trade, Challenge, Pursue, and Use_MI.
- **Phase 27 (current, closes the `ActionCode` decoding arc started in
  Phase 11)**: Trail decoding, plus a deliberate, documented exclusion
  for Succ_Trail. `turn/trail_decode.py` decodes `obj` as a target
  character id -- the same shape as Pursue/Challenge, but confirmed
  bare (no Encounter Plan tactic list) three independent ways: the
  Italian rulebook states it outright ("il primo non genera un Piano
  d'Incontro, il secondo invece sì" -- "the former doesn't generate an
  Encounter Plan, while the latter does"), `DEF2.PAS`'s `R_HPlan`
  structurally (Trail's only appearance there is a moderator-only,
  no-extra-data stealth-bonus side effect, `Trail,ASpy: cover[sldr]:=
  Spy`), and the official `AKMOVES.TXT` example sheet (Pursue's tactic
  line is filled in, `CA-FI,ME`; Trail's own is blank). Rulebook [3.17].
  **`ActionCode.SUCC_TRAIL` is deliberately excluded from
  `SUPPORTED_ACTIONS`** -- not left undecoded like everything above, but
  concluded to be *structurally impossible* to ever appear in a player
  move-submission file: an exhaustive search of every
  `lactions[...] :=` assignment across all 14 available `.PAS` files
  found no site that ever sets a phase's action to `Succ_Trail` (only
  the enum declaration and one *read* site, `RUMORS.PAS`'s `Set_Intel`,
  which consumes the moderator's own post-turn-simulation in-memory
  state -- not anything parsed from a move file); no `W_HPlan` writer
  path exists for it either; and it has no rulebook section, no
  move-sheet example, and zero real occurrences. The code that would
  produce it (rewriting a resolved Trail phase's action in memory) lives
  in the main turn-simulation engine, which was never included in this
  project's available Pascal source (only the library/plan-I-O/
  report-generation layers survive; the real engine exists only as the
  compiled `AK.EXE`/`AK.OVR`). See `turn/plan_dispatch.py`'s module
  docstring for the full reasoning, and its test suite for a regression
  test guarding against silently "completing" it later without
  revisiting this. `plan_dispatch.py` now dispatches **21 of 22**
  `ActionCode`s -- its practical maximum, given the available evidence.
- **Phase 28 (current)**: wires the three battle subsystems built
  standalone since Phase 8 (`turn/duel.py`, `turn/pursuit.py`,
  `turn/multiple_contingents.py`) into `turn/battle_orchestrator.py`.
  - **Duel** ([7.1]): each side's armies are grouped by `commanded_by`
    into `Commander`s (contingent size = army count; `tactical_ability`
    is always 0 -- `GameState` has no per-leader ability data yet, a
    documented gap **fixed in Phase 30**, see below). Defenders fall back to
    `provincial_garrison_commander()` for unled armies, per the
    rulebook's explicit fallback; attackers have no such fallback, so a
    duel only happens when the attacker side has at least one led army
    -- which no existing pre-Phase-28 test fixture did, so this change
    was non-breaking for all of them. Since the duel's own fight still
    needs the unbuilt Special Encounter Plan system [5.10], its outcome
    is approximated the same way Pursuit's own one-on-one standstill
    check already was: `estimate_win_probability()` compares the two
    commanders' own led units' total strength, rng picks the loser, and
    `apply_duel_demoralization()` reduces that loser's own led units by
    25% *before* the main battle resolves. `BattleReport` gains
    `attacker_commander_leader_id`/`defender_commander_leader_id`/
    `duel_loser_side`.
  - **Pursuit** ([7.3]): once a side is judged clean-swept with
    `loser_retreats=True`, before its armies retreat/disband, the
    winning side's units get a chance (`select_pursuers()`) to catch
    and destroy some of them (`resolve_pursuit()`) -- per that module's
    own documented requirement, each retreating army's strength for
    this specific check is recomputed one quality level down with the
    defender bonus. Caught armies are removed outright
    (`BattleReport.pursuit_destroyed_army_ids`) instead of ever reaching
    the existing retreat/disband logic. This inserted new rng
    consumption into every clean-swept-retreat code path, so every
    affected existing `ScriptedRandom` sequence in
    `tests/test_battle_orchestrator.py`/`tests/test_move_execution.py`
    needed its exact roll position re-derived and updated (documented
    inline in each test).
  - **Multiple Contingents** ([7.8]): a new, separate entry point,
    `fight_multi_attacker_battle()`, for when several leaders attack the
    same province in the same phase -- it partitions them via
    `group_attackers_into_battles()` (same origin -> very likely unite;
    different origins -> probably separate) and calls `fight_battle()`
    once per resulting group. ~~Not automatically invoked from
    `execute_move()`/`plan_dispatch.py`~~ **reachable from real
    multi-leader play as of Phase 45** via `turn/turn_processor.py
    run_turn()` -- see that phase's note below. Two more documented
    simplifications specific to this new function: which allied
    kingdom claims a jointly-won province isn't specified by the
    rulebook, resolved here as "whichever contributed the largest
    contingent" (mirroring [7.1]'s own Supreme Commander principle);
    and `fight_battle()`'s own single-`attacker_kingdom_id` signature
    means a united multi-kingdom group's defender-ally check only runs
    against the *claiming* kingdom's alliances, not every member's.
- **Phase 29 (current)**: real Cast execution (`turn/cast_execution.py`),
  but only for 2 of the 12 real spells observed in sample data --
  `turn/cast_decode.py` still decodes all of them, this phase adds a
  `GameState`-mutating resolver only where a rulebook-clear effect maps
  onto mechanics this project already has:
  - **Charm**: assigns the co-located target character to the caster's
    kingdom (rulebook [4.22]: "a Hero in same province") -- the same
    `LeaderState.kingdom_id` mechanism Hire uses (Phase 17), but
    *without* Hire's "must already be independent" requirement: nothing
    read so far restricts Charm to unemployed Heroes the way Hire's own
    section does, and "Charm" plausibly steals allegiance from *any*
    co-located character -- a documented interpretation, not a sourced
    distinction. No gold cost (a spell, not a payment).
  - **Kill_Enemy**: removes the co-located target character from
    `GameState` entirely (new `GameState.remove_leader()`, mirroring
    army destruction).
  - **Every other real spell stays unexecuted**, each with its own
    documented reason in `turn/cast_execution.py`'s docstring --
    **Resurrection** most notably can't be executed even conceptually
    with today's data model (not just "not modeled yet"): its rulebook
    target is "a deceased character," but `GameState` has no registry of
    dead/removed leaders to revive from -- once a `LeaderState` is
    deleted (by Kill_Enemy or otherwise), their data is gone, not
    archived, so there's nothing to resurrect *from*. The remaining
    spells (Bless, Plague, Flood, Tornado, Illus_Armies, Oratory,
    Part_Sea, Illus_Terrain, Skeletal_Army) have real rulebook
    descriptions of *what* they conceptually do but **no numeric effect
    magnitude anywhere** in the rulebook text read so far or in the
    available Pascal source -- inventing tax/army/quality numbers for
    them would break this project's own sourcing standard, so they stay
    decode-only.
  - **The success/failure roll itself ([3.10]: "15% plus 15% per
    level") is also not modeled this phase** -- resolving it needs the
    caster's own skill level in the spell's Magical ability, and
    `GameState` doesn't carry per-leader ability data yet (the same
    blocking gap already flagged for Practice, Phase 21 -- the move
    file only exposes the *King's* skill pairs, and even those aren't
    persisted into `GameState`). Every co-located, valid-target
    Charm/Kill_Enemy attempt currently always succeeds -- an
    incremental simplification with direct precedent: Recruit executed
    without its per-turn limits in Phase 12, gaining them in Phase 15.
    **Fixed in Phase 30**, see below.
- **Phase 30 (current)**: per-leader ability data -- adds
  `LeaderState.skills: SkillTable | None` (`models/game_state.py`),
  reusing Phase 1's already-resolved `models/kingdom.py SkillTable`
  rather than inventing a new shape, and wires it into the three
  consumers that were previously hardcoded to their pre-ability
  placeholder behavior:
  - **Duel's `tactical_ability`** ([7.1]) and **the battle-strength
    formula's Tactical/Naval bonus** ([6.3]: "+20%/level") are now read
    from the same place: `battle_orchestrator.py`'s
    `_select_side_commander()` picks each side's Supreme Commander
    *before* `_build_battle_units()` runs (previously commander
    selection happened only inside the Duel step, after units were
    already built), looks up that leader's real skill level via
    `LeaderState.skills.pair_for_ability()`, and feeds it to *both* the
    Duel tiebreak *and* `compute_effective_strength()`'s
    `combat_ability_level` for every unit on that side -- one single
    source of truth instead of two independently-derived answers that
    could disagree.
  - **Cast's success/failure roll** ([3.10]: "15% plus 15% per level,"
    requiring "a skill level of 1 or higher") is now real for Charm and
    Kill_Enemy: `cast_execution.py _roll_cast_success()` looks up the
    caster's level in the spell's Magical ability (Charm→Psychic,
    Kill_Enemy→Necromancy, the Phase 23 grouping), fails outright below
    skill 1 ("insufficient skill"), and otherwise rolls the real
    `15% + 15%*level` chance.
  - **Backward-compatible by construction**: `skills` defaults to
    `None`, and every consumer falls back to its exact pre-Phase-30
    behavior when it is -- ability level 0 (no strength/duel change) and
    Cast always succeeding. Confirmed by running the full suite after
    each change: the battle-orchestrator refactor only broke the 5
    white-box tests that called its rewritten private functions
    directly (fixed to match the new signatures, plus one new test for
    the real-skill tiebreak); every black-box `fight_battle()` test
    passed unchanged, since no pre-existing fixture ever combined
    `commanded_by` with `skills`.
  - **No parsing pipeline populates this from real move files yet** --
    confirmed by exhaustive search at the time, there was no bridge
    anywhere from Phase 1's parsed `models.kingdom.Kingdom.skills` (the
    *King's* ability pairs, straight off the move file) into any
    `GameState`/`LeaderState`. Every `GameState` in this project, in
    every test and in any real usage at the time, was hand-built by its
    caller; `skills` only ever had a real value when a caller set it
    explicitly. **A narrow bridge now exists -- see Phase 31, below.**
  - ~~**Practice ([3.13]) is still not executed** despite now having the
    ability-data piece it was missing -- see Phase 21's note above and
    the "Not yet implemented" section below: its other two gaps
    (province-level multi-character grouping, and a dice-roll procedure
    with no available Pascal source) are untouched by this phase, so it
    stays decode-only.~~ **Executed as of Phase 44** -- see that phase's
    note below (the dice-roll procedure turned out to be fully sourced;
    only the multi-character grouping stays unresolved).
- **Phase 31 (current)**: `turn/kingdom_bridge.py`
  `sync_leaders_from_kingdom()`, a first (deliberately narrow) bridge
  from a parsed move file (`models.kingdom.Kingdom`) into a persistent
  `GameState`, closing part of the gap Phase 30 flagged.
  - **Why it's narrow**: a `.K1` move file is an *order submission*, not
    a state snapshot -- it has no location, race, alignment, home
    province, or treasury for anyone (those live in the original
    engine's save-game state, never part of this project's available
    Pascal source). So this module can't fabricate a new `KingdomState`
    or `LeaderState` out of thin air; it only **enriches
    `LeaderState`s that already exist** in the `GameState` passed in
    (created by whatever turn-0 setup or prior-turn processing the
    caller already did).
  - **What it actually syncs**, for every `Leader` in `kingdom.leaders`
    with a matching existing `LeaderState`: `kingdom_id` is set to
    `kingdom.header.kingdom_number` for all of them (a leader appearing
    in Kingdom N's move-file submission this turn is, by construction,
    in Kingdom N's service this turn); and the King's own real
    `SkillTable` (`Kingdom.skills` -- no other leader's ability data is
    ever present in a move file) is attached to his `LeaderState.skills`
    specifically -- identified by matching `leader.name ==
    kingdom.king_name` (empirically always the first leader block in
    every sample file, but matched by name here as the actual invariant
    the file encodes, not an assumption that the King is always id 1).
  - **`KingdomBridgeReport`** makes the "enrich, don't create" behavior
    observable rather than silent: `synced_leader_ids`,
    `not_found_leader_ids` (present in the file, no matching
    `LeaderState` yet -- left uncreated, not an error),
    `skills_attached_to_leader_id`, and `king_not_identified` (no
    leader's name matched `king_name` -- never observed in real sample
    data, but the module doesn't guess a King in that case rather than
    risk it).
  - **Still unsolved**: populating a brand-new `GameState` from nothing
    at turn 0 -- there's no source of location/race/alignment/treasury
    anywhere in this project's available data to do that safely. This
    bridge only ever helps once *some* prior setup has already given a
    leader a `LeaderState` to enrich.
- **Phase 32 (current)**: nested-plan dispatch. `run_leader_plan()` now
  actually dispatches `PlanPhase.nested_plan` (parsed since Phase 18, but
  never executed until now) -- closing the gap every phase note since
  then has pointed back to.
  - **Confirmed against `HostAK/TP/DEF2.PAS`** (the move-file *reader*,
    per the user's standing instruction to check the original Pascal
    program before implementing anything): `R_HPlan`'s own `CASE
    lactions[m] OF` has exactly two arms that call `Read_HPlan`
    (recursively read a nested character's own plan) -- `Hire: BEGIN
    totspent:= totspent+tl; Read_HPlan; END` and `Read_More`'s `Charm,
    Resurrection: Read_HPlan`. No other action ever nests a plan; this
    matches `models/plan.py`'s existing Phase 18 docstring exactly, now
    double-checked directly against the source line numbers
    (`DEF2.PAS` ~475-517) rather than taken on trust from that earlier
    note.
  - **What actually happens**: after a phase's own dispatch succeeds,
    if it set `nested_plan` *and* really brought a character into the
    kingdom this turn -- `HireExecutionResult.hired` or
    `CastExecutionResult.applied` -- the nested character's plan is
    dispatched the same way, recursively, via the same `run_leader_plan`
    (so a nested character's own Hire/Charm can nest again; confirmed to
    happen for real in `AK3__T9.K1`, leader 72's Resurrection-nested
    plan contains its own Hire-nested plan three levels deep). Checking
    `applied` rather than inspecting the spell is what keeps
    Resurrection's own real embedded plans (present in several sample
    files, e.g. `AK3__T6.K1` leader 18's P3) from ever dispatching --
    `execute_cast` never executes Resurrection at all, so `applied` is
    always `False` for it, nested plan or not.
  - **Still "enrich, don't create"**, same rule as Phase 31's bridge: a
    nested character with no existing `LeaderState` in `state` (nobody
    set one up) is silently skipped, not fabricated.
  - `PhaseDispatchResult` gained a `leader_id` field so a flattened,
    multi-leader results list (the outer leader's phases interleaved
    with any nested characters') stays traceable to who actually issued
    each phase.
  - Real-file coverage: `AK3__T5.K1` leader 58's Hire of hero 38 (a
    single nested LMOVE), `AK3__T2.K1` leader 1's Charm of character 30
    (two nested Practice phases), and `AK3__T6.K1` leader 18's
    Resurrection of character 22 (real nested plan, confirmed never
    dispatched).
- **Phase 33 (current)**: the nemesis penalty (rulebook [6.3]: 2/3
  strength) is now actually applied in the main battle line, closing a
  gap `turn/battle_orchestrator.py`'s docstring had flagged since Phase
  9 -- `turn/strength.py compute_effective_strength`'s own
  `opponent_army_type` parameter could only ever apply it against one
  known opponent given upfront (a 1v1 check), but the main battle's real
  column pairings only exist *inside* `turn/battle_resolution.py
  resolve_battle`, after line-up runs -- so that's where the fix lives:
  a new `turn/battle_line.py apply_nemesis_penalties(attacker_columns,
  defender_columns)`, called right after `assign_battle_lines` and
  before front-line luck.
  - **Column-pairing interpretation (documented, not verbatim rulebook
    text)**: every unit in a column -- front line and any stacked
    rearward units -- is checked against the *opposing* column's own
    front-line unit's `ArmyType`, not a same-depth counterpart. Anchored
    in the one place nemesis and depth are discussed together in the
    rulebook: the Tactical-ability switch rule, "The switch will only be
    made if the army strength of the current front-line unit is less
    than the strength of a rearward unit, **after adjustments are made
    for all nemesis effects**" -- which only makes sense if a rearward
    unit's nemesis-adjusted strength is judged against whoever is
    *currently at the front* of the opposing column, the same unit it
    would actually face if switched in.
  - **Newly-discovered, still-open gap while researching this**: that
    same Tactical-ability switch mechanic (`switch_chance`,
    `maybe_switch_front_line`, implemented since Phase 6) is itself
    **never called from `resolve_battle`/`battle_orchestrator.py`** --
    confirmed by grep, zero call sites outside `turn/battle_line.py`'s
    own module. Not something this phase touches (a separate, distinct
    gap from the nemesis penalty, even though the rulebook discusses
    them in the same breath) -- flagged honestly rather than silently
    left for a future phase to rediscover.
  - Non-breaking: full suite passed unchanged before adding new tests,
    since no pre-existing fixture pairs nemesis-related `ArmyType`s
    against each other.
- **Phase 34 (current)**: the Tactical-ability switch mechanic
  (rulebook [7.2]) discovered-but-not-fixed at the end of Phase 33 is now
  wired in. `turn/battle_line.py apply_tactical_switches()` runs right
  after line-up, *before* `apply_nemesis_penalties` -- the nemesis
  penalty now applies to the final, possibly-just-switched lineup rather
  than the raw one.
  - **Re-checked against `RULES.AK` directly** (per the user's standing
    instruction to verify against the original source before
    implementing): "Switches can only be made within the same column,
    and the defender always gets the last chance to switch. The switch
    will only be made if the army strength of the current front-line
    unit is less than the strength of a rearward unit, after adjustments
    are made for all nemesis effects." Confirmed: switches are per-column
    only (no cross-column swaps), and the defender's decision comes
    strictly after the attacker's -- implemented as sequential per-column
    processing, so the defender's nemesis-aware comparison reads the
    attacker's *already-decided* front-line type at that column, not
    whatever it was before the attacker's own switch. Verified with a
    dedicated test constructing a case where the defender's swap would
    *not* trigger against the attacker's original front but *does*
    trigger against its post-switch front.
  - **Nemesis-aware but not persistent during the decision itself**: the
    switch check uses a fresh, ephemeral nemesis-adjusted comparison
    (`_nemesis_aware_strength_key`, shared with `apply_nemesis_penalties`)
    against the opposing column's *current* front-line `ArmyType` --
    without mutating any unit's real `effective_strength`. The persistent
    strength adjustment still comes from `apply_nemesis_penalties`,
    called afterward against the final lineup, so column-strength math
    and the switch decision can never disagree about what "nemesis-
    adjusted" means.
  - **Ability source**: `resolve_battle` gains
    `attacker_tactical_ability`/`defender_tactical_ability` (default 0,
    exactly preserving pre-Phase-34 behavior). `fight_battle`
    (`turn/battle_orchestrator.py`) threads through the same
    terrain-aware ability level Phase 30 already derives for the
    strength bonus and Duel tiebreak -- one commander ability level now
    drives three rulebook effects instead of three independently-derived
    numbers. The rulebook's switch-chance sentence just says
    "Tactical-Ability" with no Sea-battle exception, so reusing the same
    terrain-aware (Tactical-or-Naval) value here is a documented
    consistency choice, not a separately sourced rule.
  - **Provably non-breaking without touching any existing test**: since
    `assign_battle_lines` always deals units out strongest-first, a
    column's front unit is *structurally* guaranteed to already be its
    own maximum by raw strength -- the switch-eligibility check
    (`rearward strength > front strength`) can only ever pass when
    nemesis adjustment specifically discounts the front unit. No
    pre-existing fixture anywhere in this project pairs nemesis-related
    `ArmyType`s, so with the new parameters defaulting to 0 the eligible
    branch is never reached and zero new `rng` calls are consumed --
    confirmed empirically (full suite passed unchanged both right after
    wiring `resolve_battle` and again after threading `fight_battle`,
    before any new tests were added).
  - `BattleColumnResult` gains `attacker_switched`/`defender_switched`
    bool fields, same observability pattern as the existing luck-event
    fields.
- **Phase 35 (current)**: two of the three remaining unwired [6.3]
  strength factors flagged since Phase 9 -- fanaticism and
  desert-without-camels -- are wired into
  `turn/battle_orchestrator.py _build_battle_units`. The third,
  exploration-advantage, stays unwired -- see below for why.
  - **Desert without camels**: `RULES.AK`'s "Special rules" section is
    exact: "In a desert battle, one camel unit should be present (it
    sees double duty as a supply train.) If not, all armies have their
    quality reduced by 1 level." Checked once per side (not per unit):
    if the battle's terrain is Desert and that side's armies include no
    `ArmyType.CAMEL_CORPS`, every unit on the side gets the penalty; if
    one *is* present, nobody on the side gets it -- including the camel
    unit itself, since it's presence alone that matters, not who's being
    checked. Deliberately narrower than the "Beasts" nemesis-table grouping
    (Elephants + Camel Corps): the rule names "Camels" specifically, not
    Beasts, so an Elephant doesn't count. Fully deterministic (no `rng`
    involved), and confirmed zero pre-existing test anywhere uses
    `Terrain.DESERT` in a battle context, so this was wired in
    unconditionally with no regression risk.
  - **Fanaticism**: "An army fighting for a Divine kingdom has a 50%
    chance of becoming fanatical... Good kingdom... 40%... Evil
    kingdom... 25%" -- already implemented since Phase 5
    (`turn/strength.py roll_fanaticism`/`FANATICISM_CHANCE`), just never
    called. Now rolled once per army via a new `apply_fanaticism: bool`
    parameter threaded through `_build_battle_units` /
    `fight_battle` / `fight_multi_attacker_battle`, **defaulting to
    `False`**. Unlike `combat_ability_level`/the Phase 34 switch
    abilities, there's no natural "data absence" condition to lean on
    here -- every `KingdomState` always has a concrete `Alignment`, often
    one with a real nonzero chance (`Alignment.GOOD` alone appears in 7
    ``test_battle_orchestrator.py`` fixtures at a real 40% chance) -- so
    an unconditional roll would silently consume a new `rng.random()`
    call for essentially every unit in most existing battle tests,
    perturbing scripted sequences project-wide for a mechanic most
    callers don't need precision on. `apply_fanaticism and
    roll_fanaticism(...)` short-circuits, so the roll -- and its `rng`
    call -- never happens at all when the flag is off, confirmed
    empirically (full suite passed unchanged before any new tests were
    added). A caller that wants realistic fanaticism opts in explicitly.
    "A Skeletal army fighting under an Undead character will always be
    fanatical" (`roll_fanaticism`'s `always_fanatical` override, already
    built) is never triggered by this wiring: `Skeletal_Army` is a Cast
    spell effect this project doesn't execute (see Phase 29's note), so
    no `ArmyState` representing one can exist yet -- not an oversight,
    a consequence of a gap documented elsewhere.
  - **Exploration-advantage stays unwired, and not for lack of trying**:
    `models/game_state.py ProvinceState.explored_percent` is a single
    value per province, shared by whoever's asking -- not one per
    kingdom. The rulebook's factor needs "own side's exploration of this
    province vs. the enemy's," but this project's data model has no way
    to represent two different kingdoms' independent knowledge of the
    same province at all. This is a genuine structural gap, not a guess
    avoided: fixing it would mean redesigning how every
    Explore/Move-triggered partial-exploration write updates state
    (`turn/move_execution.py`, `turn/plan_dispatch.py`'s own EXPLORE
    branch) to track per-kingdom percentages instead of one shared
    number -- a larger, separate future task, not attempted here.
- **Phase 36 (current)**: `turn/move_execution.py execute_move()` now enforces rulebook
  [7.6]'s contested-province move restriction -- the first of
  `turn/contested_province.py`'s three functions to actually get called
  from anywhere (`is_illegal_move_from_contested`, implemented since
  Phase 8 but unwired ever since).
  - **Exact quote**: "The leader who invaded the contested province will
    execute his orders in the next phase, except that it's illegal to
    move from a contested province to an adjacent enemy province. You
    can, however, move from a province owned by a neutral player-King to
    an enemy province."
  - **Kingdom-matching interpretation**: "contested" here means
    contested *by the mover's own kingdom*
    (`ProvinceState.contested_by_kingdom_id == kingdom_id`), not merely
    contested by anyone -- the quote is specifically about "the leader
    who invaded," i.e. the attacker still stuck there from an earlier
    inconclusive battle, not some unrelated third kingdom's army that
    happens to be passing through a province someone else is contesting.
    A dedicated test confirms a province contested by a *different*
    kingdom doesn't restrict this mover. The quote's second sentence
    ("you can... move from a neutral province") needed no separate
    code path -- it's just the ordinary, uncontested case already
    handled.
  - **No new tracking needed**: `contested_by_kingdom_id` has been
    correctly set (on a mixed/tied battle result) and cleared (on
    conquest or a repelled invasion) by `turn/battle_orchestrator.py
    fight_battle()` since Phase 9 -- this phase only adds the read side
    that was missing, raising `ValueError` the same way every other
    illegal-move precondition in `execute_move()` already does.
  - **Still out of scope**: `contested_province.py`'s other two
    functions (`attacker_can_force_rebattle`,
    `contested_battle_movement_cost`) -- automatically forcing a
    rebattle "in the next phase" without a new player order needs
    tracking state across phases for a given province, well beyond this
    phase's scope. ~~`turn/plan_dispatch.py run_leader_plan` processes
    one leader's phases at a time, with no notion of "re-trigger a
    battle here next phase regardless of what this leader ordered"~~
    **a genuinely phase-by-phase, multi-leader orchestrator now exists**
    (`turn/turn_processor.py run_turn()`, Phase 45), but this specific
    mechanic isn't wired into it yet -- see that phase's note below.
  - Non-breaking: full suite passed unchanged before adding new tests,
    since `contested_by_kingdom_id` defaults to `None` and no
    pre-existing fixture sets it.
- **Phase 37 (current)**: Whales' special rule, verified against the
  English `RULES.AK` directly (not the Italian working-notes
  transcript, which turned out to paraphrase a different, related rule)
  -- verbatim: **"Whales: When fighting in any terrain other than Sea,
  they have zero strength. However, if they lose a battle in such
  terrain, they can retreat into a Sea hex automatically without fear of
  being destroyed."** Two changes:
  - **Zero strength off-sea** (`turn/strength.py
    compute_effective_strength`): an unconditional early-return `0.0`
    for `ArmyType.WHALES` off-sea, replacing the generic adverse-terrain
    *halving* `ARMY_TABLE`'s own Whales row would otherwise apply --
    "zero," not "reduced." Bypasses every other factor in the pipeline
    (quality, defender bonus, fanaticism, etc. would all just multiply a
    nonzero base by something).
  - **Guaranteed Sea retreat** (`turn/battle_orchestrator.py
    fight_battle`): a clean-swept Whale army fighting in non-Sea terrain
    now always retreats to the nearest adjacent Sea-terrain province
    (`_whale_sea_retreat_destination`, any ownership -- the rulebook
    says "a Sea hex," not "a *friendly* Sea hex," unlike the ordinary
    retreat rule) -- bypassing both the `loser_retreats` flag (checked
    *before* the existing `elif ... and loser_retreats` branch) and the
    outright-destroy branch entirely, and regardless of quality (a GREEN
    Whale retreats instead of disbanding).
  - **Two documented edge cases, not silently guessed around**: if no
    adjacent province is Sea terrain at all, `_retreat_or_disband` falls
    back to its ordinary quality-based disband/mercenary rule -- the
    rulebook's guarantee can't be literally honored without a Sea hex to
    retreat to; and Pursuit ([7.3]) isn't exempted -- a retreating Whale
    can still be caught and destroyed by `_apply_pursuit` before this
    branch is even reached, since the rulebook's guarantee is
    specifically about the *ordinary, no-destination* disband path, not
    the separate pursuit mechanic.
  - Non-breaking: full suite passed unchanged after both changes, before
    any new tests were added -- no pre-existing fixture uses
    `ArmyType.WHALES` at all.
- **Phase 38 (current)**: Fleets' own special rule, the "still missing"
  item re-confirmed while researching Phase 37 -- `RULES.AK` [7.2]
  verbatim: **"Fleets fighting on land provinces would generally be
  reduced to Depleted status instead of being eliminated."** A
  different, separate exception from Whales' own: no forced retreat,
  just quality forced to `Quality.DEPLETED` *in place* instead of
  removal from `state`.
  - **Only two of `fight_battle`'s branches actually remove an army from
    `state`, so only those two needed intercepting**
    (`_fleet_avoids_elimination`, `turn/battle_orchestrator.py`): the
    outright "clean-swept, `loser_retreats=False`" destroy branch, and
    `_retreat_or_disband`'s "no retreat destination, GREEN/DEPLETED"
    disband branch (which now takes a new `avoid_elimination: bool`
    parameter). A successful ordinary retreat already avoids elimination
    on its own (no change needed), and becoming a mercenary (the
    AVERAGE-or-better "no retreat destination" branch) already isn't
    elimination either -- confirmed by a dedicated test that an
    AVERAGE-quality Fleet with no retreat destination still becomes a
    mercenary as before, quality untouched.
  - Same non-extension to Pursuit as Whales (Phase 37), for the same
    reason: the rulebook's "not eliminated" guarantee is specifically
    about the battle-resolution elimination decision, not the separate
    [7.3] pursuit mechanic -- a retreating Fleet can still be caught and
    destroyed by `_apply_pursuit`.
  - Non-breaking: full suite passed unchanged after wiring, before any
    new tests were added -- no pre-existing fixture uses
    `ArmyType.FLEET` in a battle context.
- **Phase 39 (current)**: the last item from Phase 38's own "still
  missing" list -- non-humanoid rear-targeting, rulebook [7.2]
  verbatim: **"Non-humanoid units (Eagles, Dragons, Whales and Mermen)
  can attack from above or below... If there is an enemy unit behind
  the front lines for the non-human unit to attack instead of a unit on
  the front line, it will attack the rear unit instead (the non-human
  unit and the rearward unit will both be at 100% strength in this
  case.)"**
  - **Discovered while implementing this**: `turn/battle_line.py
    column_strength`'s `outflank_second_line` parameter -- which boosts
    an ordinary column's own second-line unit from 50% to 100% -- was
    already fully built (since Phase 6) but, like the Tactical-ability
    switch before Phase 34, **never actually wired into
    `resolve_battle`**. Rather than build a second, parallel mechanism,
    Phase 39 reuses it: a new `turn/battle_line.py
    column_has_overflight_unit(column)` helper checks whether the
    *opposing* column contains an overflight unit (any depth -- they
    "attack from above or below" regardless of their own position, the
    same reason they already contribute 100% themselves), and
    `resolve_battle` now drives `outflank_second_line` from that check
    for each column.
  - **One parameter, two distinct triggers, both documented on
    `column_strength` itself**: the rule this parameter was originally
    named for -- "a force superior in numbers may outflank... they
    count as 100% instead of 50%" -- depends on `terrain_line_length_cap`
    eligibility this module can't derive, and **remains unwired, a
    separate, still-open gap**, distinct from rear-targeting even though
    both happen to produce the identical numeric effect.
  - ~~**Druidic-ability carve-out not modeled**: "if the non-human unit
    has low strength because its leader has insufficient Druidic
    ability, it will be held back and will throw its low strength into
    the attack on the front-line unit" (i.e. no rear-targeting in that
    case) -- skipped at the time of writing for the same reason every
    other Druidic-ability rule in this project was then skipped
    (`turn/strength.py`'s own module docstring: no "Druid Table" data
    available). **The Druid Table itself now exists as of Phase 41**
    (`turn/strength.py DRUID_TABLE`/`compute_druidic_shortfall`), so the
    underlying data gap is closed, but this specific carve-out --
    *which* units get held back from rear-targeting because of it --
    is still not wired into `battle_line.py`/`resolve_battle`; every
    overflight unit is still treated as eligible to rear-target
    regardless of its controller's Druidic ability. Left as a
    consequence of Phase 41's own deliberately narrow scope (quality
    penalty only, see that phase's note below) rather than revisited
    here.~~ **Fixed in Phase 43** -- see that phase's note below.
  - Non-breaking: full suite passed unchanged after wiring, before any
    new tests were added -- no pre-existing fixture pairs an overflight
    unit against a 2+-deep opposing column.
- **Phase 40 (current)**: the King/Hero distinction, flagged as missing
  since Phase 16-17 (and re-flagged again at Phase 25 for Challenge's
  own encounter-acceptance rules) every time Disband, Fire, or Hire's
  finer rulebook nuances came up. `models/game_state.py LeaderState`
  gains `is_king: bool = False`.
  - **`turn/kingdom_bridge.py`** (Phase 31) already had to solve "which
    leader in this move file is the King" to attach the King's own
    `SkillTable` -- `sync_leaders_from_kingdom()` now reuses that exact
    identification to set `is_king` too: `True` for the matched King,
    `False` for every other synced leader in the same file (an
    authoritative sync, not just "set True and never touch False" --
    tested by deliberately seeding a stale, backwards flag first and
    confirming the sync corrects it).
  - **Disband** (`turn/plan_dispatch.py _dispatch_disband`, rulebook
    [3.6] verbatim: *"A King may Disband any army at any time. A
    character can Disband an army only if he is in the same
    province."*): a Hero must now be co-located with each target army
    or it's silently left alone (same "skip, don't raise" convention
    already used for an unknown army id); a King bypasses the check
    entirely, as before Phase 40.
  - **Fire** (`_dispatch_fire`, [3.7] verbatim: *"A King may Fire a Hero
    at any time. A character can Fire a Hero only if he is in the same
    province."*): same pattern. `_dispatch_fire`'s own signature gained
    a `leader_id` parameter it never needed before (it had no way to
    check *who* was acting). The rulebook's co-location requirement
    already covers "a Hero can fire himself" as a trivial case -- he's
    always in his own province -- so no separate self-fire carve-out
    was needed.
  - **Hire** (`_dispatch_hire`, [3.5]: *"You can't Hire a Hero who rules
    his own province."*): now rejects a target with `is_king=True`
    outright (`reason="cannot hire a King"`), checked as its own
    explicit condition rather than left to happen as a side effect of
    the existing "hero already in service" check -- which would only
    coincidentally catch a King who happens to still have a
    `kingdom_id` set. A dedicated test uses a King *without* a
    `kingdom_id` (an edge case, e.g. a deposed King) to prove the check
    is real, not incidental.
  - **`Pick_Up` deliberately untouched**: rulebook [3.9] gives Pick_Up
    no King exception ("You can Pick Up an army led by a co-located
    character" -- no "a King may..." carve-out anywhere in that
    section), confirmed by re-reading `RULES.AK` directly rather than
    assuming symmetry with Disband/Fire.
  - **One test-infrastructure change**: `tests/test_plan_dispatch.py`'s
    shared `_state_with_army()` helper's leader is now built with
    `is_king=True` -- almost every existing test using it predates this
    distinction and was never about testing co-location, so treating it
    as the King (the same role it already implicitly played throughout
    those tests) preserves their original intent with a one-line change
    instead of touching dozens of call sites; tests that specifically
    exercise Hero co-location build their own `LeaderState` with
    `is_king=False`.
  - **Foundational for later phases**: this is the piece the Druid
    Table's own garrison-commander clause ("If a unit is under the
    garrison commander of a province, and is of a different race than
    the King, then the King's druidic ability is used...") will need --
    not attempted this phase, but no longer blocked on "which leader is
    the King" the way it would have been before.
  - Non-breaking except for one deliberate, documented test-helper
    default change (see above) -- confirmed by running the full suite
    immediately after that one-line edit, before writing any new
    Phase 40 tests.
- **Phase 41 (current)**: the Druid Table quality penalty, rulebook
  [4.32]: *"With each level, Druids gain the ability to lead armies of
  races other than their own, as listed in the Druid Table. If a
  character attempts to lead an army when he has insufficient Druidic
  ability, the quality of the army suffers a decrease equal to his
  shortfall in Druidic ability."* Resolves the `[6.3]` quality-modifier
  list's `-? insufficient Druidic ability` line, open since the earliest
  `turn/strength.py` work (Phase 21-adjacent) for lack of "Druid Table"
  data -- found by reading `RULES.AK`'s own `[4.32]` section directly.
  - **`turn/strength.py DRUID_TABLE`**: transcribed verbatim from the
    rulebook table -- Level 1: Humans, Elves, Dwarves, Orcs, Mermen,
    Werebeasts; Level 2: Whales, Trolls; Level 3: Eagles, Ents; Level 4:
    Dragons. `Race.NO_RACE`/`SAURIAN`/`VAMPISH`/`ROHAN` have no entry in
    the rulebook text available to this project -- treated as requiring
    Druidic skill 0, not guessed at a higher value.
  - **`compute_druidic_shortfall(leader_race, army_race,
    leader_druidic_skill)`**: `max(0, DRUID_TABLE.get(army_race, 0) -
    leader_druidic_skill)`, with two deliberate short-circuits to 0: (1)
    `leader_race == army_race` -- the rulebook's own framing is
    specifically about "races OTHER than their own," so a Whale leader
    commanding Whales needs no Druidic skill at all, even though
    `DRUID_TABLE[Race.WHALES] == 2` (that entry is for a *non*-Whale
    leader); (2) `leader_race is None` -- an independent Hero has no
    kingdom to derive a race from, treated as insufficient data rather
    than a guessed penalty.
  - **Wired into `turn/strength.py modified_quality`/
    `compute_effective_strength`** as a new `druidic_shortfall: int = 0`
    parameter, subtracted from the quality level in the documented
    `[6.3]` order (after desert-without-camels, before the
    home-province/fanatical additions), then clamped to `Quality`'s
    range same as every other modifier there.
  - **Wired into `battle_orchestrator.py _build_battle_units`**
    (`_druidic_shortfall_for`): for a *led* army (`commanded_by` is not
    `None`), the leader's own race and the army's race are both derived
    the same way every other per-leader/per-army race lookup in this
    project already is -- via `kingdom_id -> KingdomState.race`, since
    no per-character race field exists. The leader's Druidic skill comes
    from `LeaderState.skills.pair_for_ability(Ability.DRUID)[0]`, or `0`
    if that leader has no `skills` recorded (the same placeholder
    convention used for Tactical/Naval ability since Phase 30). Fully
    deterministic, no `rng` involved, so wired in unconditionally (same
    precedent as desert-without-camels).
  - **Structurally a no-op for the overwhelmingly common case**: a
    leader's own race always equals his own army's race when both
    belong to the same kingdom, which is virtually every army in this
    project. The mismatch this rule is actually for is only reachable
    via `Pick_Up` attaching a co-located army regardless of ownership,
    or an army's owning kingdom changing after `Leave`/`Disband` --
    confirmed empirically: the full suite passed unchanged (833 -> still
    833) the moment this was wired in, before any new Phase 41 tests
    were added.
  - ~~**Deliberately unmodeled**: the rulebook's own carve-out for
    *unled* armies under the garrison commander ("If a unit is under the
    garrison commander of a province, and is of a different race than
    the King, then the King's druidic ability is used...") is not
    covered -- resolving it would mean `_build_battle_units` looking up
    *which* King owns the province the battle is in (not necessarily the
    army's own kingdom), a province-ownership lookup this function isn't
    currently wired for. Left unmodeled, the same "garrison commander
    has no special abilities" simplification this project already uses
    for Tactical ability's own Duel fallback ([7.1]). This is exactly
    the piece Phase 40's `is_king` flag was built as a foundation for,
    per that phase's own note above -- still not attempted this phase.~~
    **Fixed in Phase 42** -- see that phase's note below.
  - Also **not extended to `battle_line.py`'s rear-targeting carve-out**
    (Phase 39) -- see that phase's note above, updated to reflect that
    the data gap it cited is now closed but the specific wiring isn't.
  - Non-breaking: full suite passed unchanged (833 passed) immediately
    after wiring, before any new tests were written.
- **Phase 42 (current)**: the Druid Table's garrison-commander/King-
  substitution carve-out, rulebook [4.32]: *"If a unit is under the
  garrison commander of a province, and is of a different race than the
  King, then the King's druidic ability is used"* -- the piece Phase 41
  deliberately left out, and exactly what Phase 40's `is_king` flag was
  built as a foundation for.
  - **`battle_orchestrator.py _druidic_shortfall_for`** now branches on
    `army.commanded_by`: a led army keeps Phase 41's own leader-based
    path unchanged; an unled army (`commanded_by is None`) now routes
    through a new `_king_druidic_shortfall_for`.
  - **`_king_druidic_shortfall_for`**: resolves the battle province's
    *owning* kingdom via `ProvinceState.owner_kingdom_id` -- not
    necessarily the unled army's own `kingdom_id`, since the rulebook is
    explicit that it's the King, not the garrison commander or the
    army's own allegiance, whose ability is substituted (an allied army
    defending alongside the owner's garrison is still judged against the
    *owning* kingdom's King). That kingdom's King is found via a new
    `_find_king_of_kingdom` helper -- a linear scan of `state.leaders`
    for a `kingdom_id` match with `is_king=True`, reusing Phase 40's flag
    for exactly the purpose flagged when it was built. No owning
    kingdom, or no King identified for one (an edge case this project's
    data can't always resolve, e.g. a captured province with no
    surviving King on record), falls back to 0 -- insufficient data, not
    a guessed penalty, same convention as every other Druidic-shortfall
    edge case in Phase 41.
  - **Same same-race bypass reused as-is**: `compute_druidic_shortfall`
    already treats `leader_race == army_race` as 0 regardless of skill,
    which is exactly right here too -- an unled army whose own race
    matches the province-owning King's race needs no Druidic check,
    matching the rulebook's "of a different race than the King" framing
    with zero new logic.
  - ~~**Not extended to `battle_line.py`'s rear-targeting carve-out**
    (still open, see Phase 39/41's notes above) -- this phase only
    closes the quality-penalty gap for unled armies, not the separate
    "held back from rear-targeting" behavior tied to the same rulebook
    sentence.~~ **Fixed in Phase 43** -- see that phase's note below.
    Since Phase 43's own flag is derived from the *same*
    `druidic_shortfall` value this phase already computes (via
    `_druidic_shortfall_for`, King-substitution included), an unled
    overflight army under the garrison commander gets
    `druidic_rear_targeting_blocked` set correctly too, with no
    additional wiring needed -- this phase's own scope already covered it
    once Phase 43 landed.
  - Non-breaking: full suite passed unchanged (845 passed) immediately
    after wiring, before any new tests were written. 5 new tests added
    (850 passed total).
- **Phase 43 (current)**: the rear-targeting Druidic-ability carve-out,
  rulebook [4.32]/[7.2]: *"if the non-human unit has low strength
  because its leader has insufficient Druidic ability, it will be held
  back and will throw its low strength into the attack on the
  front-line unit"* -- the last open note from Phase 39's own
  rear-targeting work, unblocked once the Druid Table existed (Phase
  41/42).
  - **`BattleUnit.druidic_rear_targeting_blocked: bool = False`**
    (`turn/battle_line.py`): a new field marking an overflight unit as
    "held back" instead of eligible to rear-target. Set by
    `battle_orchestrator.py _build_battle_units` from
    `is_overflight_unit(army.army_type) and druidic_shortfall > 0` --
    reusing the *same* `druidic_shortfall` value Phase 41/42 already
    compute per unit (`_druidic_shortfall_for`), so an unled army's
    King-substitution shortfall (Phase 42) feeds this flag automatically
    too, with zero extra wiring.
  - **`column_strength`/`column_has_overflight_unit`** (`battle_line.py`)
    now route through a new `_is_effective_overflight(unit)` helper --
    `is_overflight_unit(unit.army_type) and not
    unit.druidic_rear_targeting_blocked` -- instead of checking
    `is_overflight_unit` directly. A blocked unit falls through to
    ordinary depth-based halving in `column_strength` (ends up "throwing
    its low strength into the attack on the front-line unit," i.e.
    treated exactly like a non-overflight unit) and no longer counts
    toward `column_has_overflight_unit`, so it doesn't trigger the
    *opposing* column's own rear-targeting boost either -- both halves
    of the rulebook sentence, with one helper.
  - **Regression risk found and fixed while wiring**: three other call
    sites construct a *replacement* `BattleUnit` from an existing one
    (`battle_line.py _apply_nemesis_to_column`, `battle_resolution.py
    _apply_front_line_luck`, `duel.py apply_duel_demoralization`), and
    all three run *before* `resolve_battle`'s own
    `column_has_overflight_unit` checks. None of them originally passed
    the new field through, which would have silently reset a blocked
    unit back to "eligible" the moment nemesis, front-line luck, or duel
    demoralization touched it. All three now forward
    `druidic_rear_targeting_blocked` explicitly; covered by dedicated
    regression tests (`test_apply_nemesis_penalties_preserves_the_
    druidic_rear_targeting_blocked_flag`,
    `test_resolve_battle_druidic_blocked_flag_survives_front_line_luck`)
    that would have failed before the fix.
  - Non-breaking: full suite passed unchanged (850 passed) immediately
    after wiring, before any new tests were written. 10 new tests added
    (860 passed total).
- **Phase 44 (current)**: real Practice execution (rulebook [3.13],
  quoted in full below), the first of the three original blockers
  flagged back in Phase 21 to actually close (per-leader skill data,
  Phase 30) plus a design choice for the roll procedure -- multi-
  character coordination stays the one genuinely open piece.

  **[3.13] Practice Ability, quoted in full:**

  > If 2 or more characters are in the same province and all characters
  > Practice the same ability in a phase, and one character has a
  > higher skill in the ability (unmodified by magic items he
  > possesses), the character(s) with the lower skill in the ability
  > will rise in skill 1 level (provided he has sufficient aptitude,
  > explained below.) If the characters have the same skill level,
  > there is a 10% chance of rising 1 level for each character. A
  > character who Practices alone has a 5% chance of rising 1 level.
  > When a character Practices an ability with another character, and
  > one character has higher skill because he possesses a magic item
  > that raises his skill level, that magic item does not count and
  > both characters have only a 10% chance of improving. A character's
  > chance of rising 1 level is halved for each level beyond his
  > natural aptitude. For example, if a character has a natural
  > aptitude of 1, he has no trouble attaining level 1 in an ability,
  > but has only a 50% chance of attaining level 2, a 25% chance of
  > attaining level 3, and a 12.5% chance of attaining level 4. This
  > applies even when the character is learning from a character with
  > a higher level. The chance to increase by experience is affected by
  > aptitude in the same way. Aptitude may increase if a character is
  > due to rise in level, (either from practicing or experience), but
  > can't because of low aptitude. The chance of an aptitude increase
  > depends on the current skill level: 0: 0%, 1: 10%, 2: 25%, 3: 50%,
  > 4: 100%, 5: 80%, 6: 60%, 7: 40%, 8: 20%.

  That aptitude-rise table matches `HostAK/TP/CTME.PAS`'s ``apt_rise:
  array[0..10] OF byte = (0,10,25,50,100,80,60,40,20,0,0);`` exactly --
  found by reading `RULES.AK` directly (not the parser's own README
  quote, which had been paraphrased down to a summary before this
  phase).
  - **`turn/practice_execution.py`**, new module: `PracticeOutcome`
    (the per-attempt result) and `attempt_skill_rise(current_skill,
    aptitude, base_chance, rng)`, the shared core roll -- halve
    `base_chance` once per level the target level (`current_skill + 1`)
    sits beyond `aptitude`, roll once; on failure, **only if aptitude
    genuinely constrained the chance** (`levels_beyond_aptitude > 0` --
    i.e. actually "due to rise... but can't because of low aptitude",
    not merely unlucky on an unconstrained roll), roll a second time
    against `APT_RISE_CHANCE[current_skill]` for an aptitude increase
    instead. Both rolls clamp at `MAX_SKILL_LEVEL = 9`
    (`SkillTable`'s own documented 0-9 range, Phase 21) -- already at
    the cap is a no-op, no roll at all.
  - **Roll sequencing is a documented design choice**: no Pascal source
    shows the actual dice-roll call site for Practice (unlike, say,
    Cast's success roll or fanaticism's chance), so "one threshold roll
    per attempt" was chosen as the simplest procedure consistent with
    every other percentage mechanic already in this project.
  - **`resolve_practice_solo`** (5%), **`resolve_practice_pair`**
    (guaranteed-for-the-lower-skill-partner / 10%-each-if-tied -- the
    rulebook's own fully-sourced two-character case), and
    **`resolve_practice_group`** (an N >= 2 generalization: all-equal ->
    10% each; otherwise only the group's *minimum*-skill members get
    the guaranteed roll, everyone else gets nothing that phase -- a
    natural but **undsourced** extension, since the rulebook's own
    examples only ever describe exactly two characters, flagged as an
    interpretation in the module docstring).
  - **The magic-item override isn't modeled**: "if one character has
    higher skill only because of a magic item, both get only 10%" can't
    be evaluated since this project tracks no per-leader magic-item
    inventory or skill modifiers at all -- comparisons always use
    `LeaderState.skills`' raw current level, the same gap already
    flagged everywhere else magic items come up in this project.
  - ~~**Only `resolve_practice_solo` is reachable from
    `plan_dispatch.py`** (`_dispatch_practice` -> `execute_practice`):
    true multi-character coordination needs visibility into every other
    leader's same-phase order, which the per-leader `run_leader_plan`
    dispatch structurally doesn't have.~~ **Reachable as of Phase 46**
    via `turn/turn_processor.py run_turn()` (`execute_practice_group`)
    -- see that phase's note below. `plan_dispatch.py`'s own
    `_dispatch_practice` -> `execute_practice` still resolves solo-only
    when driven directly (e.g. via `run_leader_plan` alone, bypassing
    `run_turn`) -- **documented as a deliberately conservative
    approximation, not a guess**: 5% is the *smallest* of the
    rulebook's three base chances (100%/10%/5%), so always treating the
    acting leader as solo never overstates a rise chance, only
    potentially understates one whenever two+ leaders are genuinely
    co-practicing.
  - **`leader.skills is None` (no ability data recorded at all -- the
    common case for Heroes, per Phase 21's own finding that 74% of real
    Practice instances belong to Heroes) is treated as a fresh all-zero
    `SkillTable`**, the same "0 if unrecorded" placeholder convention
    already used everywhere else in this project for missing per-leader
    ability data (Tactical/Naval strength bonus, Druidic shortfall,
    Cast's success roll) -- attached to the leader so this and later
    Practice attempts build on it instead of resetting every time.
  - **`models/kingdom.py SkillTable`** gains `set_pair_for_ability()`,
    the symmetric write counterpart to the existing `pair_for_ability()`
    read, so `practice_execution.py` doesn't need to know the table's
    raw layout.
  - **Two abilities are explicitly out of scope this phase**:
    **Tactical** ([6.1]) doesn't raise personal skill via [3.13] at all
    -- it trains the leader's *armies*' quality tiers instead (a
    completely different mechanic touching `ArmyState.quality` across a
    whole command, with its own "needs an existing higher-tier army to
    train against" condition and multi-leader pooling) --
    `execute_practice` recognizes `Ability.TACTICAL` and returns
    `not_implemented_for_ability=True` rather than silently running the
    wrong mechanic against it. **Sage** ([4.31]) still gets its normal
    skill-rise roll here (its own skill mechanic is ordinary [3.13]),
    but the rulebook's *additional* "~5%/level device discovery" roll
    "on top of, not instead of" the skill roll isn't modeled -- no
    item/device data model exists anywhere in this project.
  - **Not fully non-breaking, as expected for a decode-only ->
    execution graduation**: 4 pre-existing `test_plan_dispatch.py` tests
    asserted `PRACTICE` dispatch returned the old decode-only
    `PracticeRequest` type -- updated to expect `PracticeExecutionResult`
    instead, the same kind of test update Phase 15 (Recruit) and Phase
    29 (Cast) needed for their own graduations. Full suite green after
    that fix (860 passed), then 20 new tests added (880 passed total).
- **Phase 45 (current)**: `turn/turn_processor.py`, a genuinely
  phase-by-phase, multi-leader turn orchestrator -- the structural gap
  behind three separate "built but not auto-invoked" notes scattered
  across Phases 28, 36, and 44: Multiple Contingents, Practice's
  multi-character coordination, and `contested_province.py`'s
  forced-rebattle rule all need the same thing, visibility into every
  leader's *same-phase* order before any of them resolve, which
  `turn/plan_dispatch.py run_leader_plan()` structurally can't provide
  (it dispatches one leader's *entire* plan before moving to the next).
  This phase builds the orchestrator and wires in the first of the
  three -- Multiple Contingents; the other two are flagged, fast
  follow-ups now that the structural blocker is gone, not attempted
  here.
  - **`run_turn(turn_leaders, state, *, board_width, ...)`** iterates
    P0..P4 *across every leader's plan at once* (`TurnLeader` pairs a
    `Leader` with its `kingdom_id`) instead of leader-by-leader. For
    each phase label: decode every LMOVE's target hex (without
    executing it yet), group same-target movers, and detect which
    groups are a real Multiple Contingents scenario -- see below --
    before dispatching anything else.
  - **Detection rule**: 2+ leaders' LMOVEs at the same phase label
    targeting the same province, where at least 2 of them each
    independently see a non-allied defending army there (the identical
    "attacking" criterion `turn/move_execution.py execute_move()`
    already uses -- a leader-only move, with no army, never counts),
    route through `turn/battle_orchestrator.py
    fight_multi_attacker_battle()` as one united scenario instead of N
    independent solo battles. A **mixed** group (some movers see the
    target as friendly, others as hostile) only routes the *hostile*
    subset through Multiple Contingents; peaceful movers dispatch an
    ordinary independent move, unaffected -- the rulebook doesn't
    address this mixed case, so no attempt is made to have a peaceful
    mover somehow "witness" or join the battle.
  - **`battle_orchestrator.py fight_multi_attacker_battle()`'s own
    return type changed**: it now returns `list[MultiAttackerBattle]`
    (`leader_ids` + the shared `BattleReport`) instead of a bare
    `list[BattleReport]` -- added so a caller driving several leaders at
    once can look up which report belongs to which leader, without
    re-deriving `group_attackers_into_battles()`'s own rng-consuming
    grouping a second time (which would desync the shared `rng`
    stream). The 3 existing `fight_multi_attacker_battle` tests were
    updated for the new wrapper (`.report` instead of direct field
    access) -- the only genuinely breaking change in this phase.
  - **Everything else reuses `turn/plan_dispatch.py` verbatim, not
    duplicated**: `_dispatch_single` wraps one `PlanPhase` in a
    throwaway one-segment `ActionPlan` and calls the existing, fully-
    tested `run_leader_plan()` on it -- including its own nested-plan
    dispatch (Hire/Charm/Resurrection still fires immediately, in full,
    exactly as before; a nested character's own LMOVE never
    participates in *this* phase's Multiple Contingents grouping, an
    already-small, documented scope limitation). The cost of this reuse:
    every `PhaseDispatchResult.segment_index` produced via `run_turn`
    reads `0` regardless of the real plan's own segment index -- lost no
    real information in practice, since real move-file data confirms
    every leader has exactly one top-level segment anyway
    (`models/plan.py`'s own docstring).
  - **Post-battle bookkeeping (movement cost, army/leader relocation)
    for the multi-attacker path is duplicated from `execute_move()`**,
    not extracted into a shared helper -- a deliberate choice to avoid
    touching the heavily-tested single-attacker path in this phase.
  - **The partial-exploration side effect for a united multi-attacker
    move is applied once per target province per phase (shared), not
    once per attacker** -- the rulebook doesn't say whether simultaneous
    arrivals compound it; a documented, unsourced design choice, the
    same category as `turn/multiple_contingents.py`'s own unite-chance
    constants.
  - **Contested-province illegal-move filtering runs per mover**, same
    as `execute_move()`'s own check: an illegal mover is excluded from
    the group (recorded as an error result, same "never raises, records
    errors" convention as `run_leader_plan`) rather than blocking the
    whole group; if fewer than 2 valid attackers remain after filtering,
    whoever's left dispatches individually and normally instead.
  - **Still explicitly out of scope**: ~~Practice's own multi-character
    coordination~~ **wired in as of Phase 46** -- see that phase's note
    below. ~~`contested_province.py`'s forced-rebattle rule still isn't
    wired into `run_turn()`~~ **wired in as of Phase 55**.
  - Non-breaking except for the documented `fight_multi_attacker_battle`
    return-type change (3 existing tests updated accordingly); full
    suite green after that fix (880 passed), then 6 new tests added in
    `tests/test_turn_processor.py` (886 passed total).
- **Phase 46 (current)**: Practice's [3.13] multi-character coordination,
  the second of the three fast follow-ups Phase 45 unblocked -- wired
  into `turn/turn_processor.py run_turn()` using the exact same
  detect-before-dispatch pattern already built there for Multiple
  Contingents.
  - **`turn/practice_execution.py execute_practice_group(state,
    leader_ids, ability, rng)`** (new): applies a co-located, same-phase,
    same-ability Practice order to 2+ leaders at once, via
    `resolve_practice_group` (the module's own fully-sourced/documented-
    generalized N >= 2 case, already built in Phase 44 but until now
    unreachable). Shares a new `_get_or_create_skills()` helper with
    `execute_practice` -- the same "fresh all-zero `SkillTable` if none
    recorded" placeholder convention, factored out rather than
    duplicated. `Ability.TACTICAL`/a raw out-of-range ability resolves
    to `not_implemented_for_ability=True` for the whole group, same as
    the solo path.
  - **`run_turn()`'s detection rule**: for each phase label, 2+ leaders'
    PRACTICE phases decoding to the *same* `Ability`, where those
    leaders' current locations (read *before* any of this phase's
    actions run, same timing as the LMOVE detection) are the *same*
    province, route through `execute_practice_group` instead of each
    resolving solo via `_dispatch_single`. **No alliance/kingdom
    requirement** -- unlike Multiple Contingents, rulebook [3.13]'s own
    text ("If 2 or more characters are in the same province...") never
    mentions kingdom membership, so this groups purely by co-location,
    across any kingdoms including enemies.
  - **Reuses `resolve_practice_group` uniformly for every group size
    >= 2**, not `resolve_practice_pair` specially for exactly 2 -- a
    correctness check done while wiring this in confirmed
    `resolve_practice_group`'s own branching (all-equal -> tied chance
    for everyone; otherwise -> only the group's minimum-skill members
    get the guaranteed roll) produces *identical* results to
    `resolve_practice_pair` for N=2 in both its symmetric and
    asymmetric cases, so no special-casing was needed.
  - Non-breaking: full suite passed unchanged (886 passed) immediately
    after wiring, before any new tests were written. 11 new tests added
    (7 for `execute_practice_group`'s own math in
    `tests/test_practice_execution.py`, 4 for the `run_turn()`
    detection rule in `tests/test_turn_processor.py` -- 897 passed
    total).
- **Phase 47 (current)**: Recruit's target-leader co-location
  validation, rulebook [3.4]: *"Any character in the province may lead
  the armies, or they can be placed under the garrison commander."*
  `turn/recruit_execution.py execute_recruit()` previously assigned
  command of a newly recruited (or newly hired mercenary) army to
  `request.leader_id` unconditionally -- never checking that leader
  actually existed as a `LeaderState`, let alone that he was co-located
  with whoever issued the Recruit order.
  - **Fix**: resolves an effective `commanded_by` once per call --
    `request.leader_id` if (and only if) that id resolves to a real
    `LeaderState` whose `location` matches the acting leader's own
    (i.e. the recruiting province); `None` (unled/garrison) otherwise.
    Applied uniformly to both the fresh-levy and mercenary-hiring
    branches. Same silent "skip, don't raise" convention already used
    for Disband/Fire/Pick_Up's own co-location checks (Phase 40) --
    an implausible target falls back to the garrison rather than
    raising or silently trusting a bogus/absent leader id.
  - **Was investigated as a candidate for the [Multiple Contingents /
    Practice-style] `turn/turn_processor.py` grouping treatment first**,
    but doesn't need it: unlike LMOVE or PRACTICE, a Recruit order's
    "who can command the result" question only depends on data already
    available to a single-leader dispatch (the acting leader's own
    location and `state.leaders`), not on what any *other* leader is
    doing this same phase -- so the ordinary per-leader path was the
    right fix, no orchestrator involvement needed.
  - Non-breaking: full suite passed unchanged (897 passed) immediately
    after wiring, before any new tests were written -- no pre-existing
    fixture exercised a target leader that was absent or elsewhere. 3
    new tests added (900 passed total).
- **Phase 48 (current)**: `turn/encounter.py`, the first slice of the
  personal-combat ("Encounter") system (rulebook [5.0]-[5.3], [5.9]) --
  the missing piece behind Search's, Challenge/Pursue's, and ASpy/
  Defend's own "remaining gap" notes above, and Duel's own approximated
  fight ([7.1], Phase 28's note). **Not yet wired into any of those** --
  a deliberately narrow first phase, the same incremental approach this
  project already used for the army-battle system (Phase 5's combat
  primitives, built up over several more phases before a full
  `fight_battle()` existed).
  - **Scope: only Melee and Fire Arrow**, the two tactics [5.0]-[5.8]
    gives concrete numbers for. `CHARACTER_HIT_POINTS = 10` ([5.0]:
    "In combat, all characters have 10 hit points"); `resolve_melee_duel`
    (flat 50% hit chance, 1-6 damage, [5.3]) and `resolve_fire_arrow_duel`
    (30% + 10%/Archery-level hit chance, 1-6 damage, a free-attack count
    equal to Archery skill, [5.2]) each assume *both* combatants use
    that one tactic for the whole encounter -- sidestepping the
    Spell/Bow/Melee range-transition state machine real mixed-tactic
    combat would need entirely, a documented scope-narrowing choice.
  - **Initiative** ([5.0]: "the character with the greater skill level
    relevant to the tactic he is using generally goes first... If the
    skill is the same, the characters go in random order"): `_acts_first`
    compares the relevant skill directly, tie broken by `rng.random()`.
  - **Neutral Kingdoms' "Order of Duelists"** ([5.0]: "+1 modifier to
    their Melee and Archery abilities"): `Combatant.neutral_duelist_bonus`
    -> `effective_melee_skill`/`effective_archery_skill`.
  - **Explicitly out of scope, each independently flagged in the module
    docstring**: Steal/Negotiate/Flee/Scout/Give ([5.4]-[5.8]); casting
    spells or using magic items in combat ([5.1], no spell/item-effect
    system exists anywhere in this project); the "about double" free
    attacks when both combatants have Archery skill ([5.2], no concrete
    formula given -- "about double", "some random chance"); what happens
    once Fire Arrow's free attacks run out with nobody dead (real combat
    would continue at Melee range -- `resolve_fire_arrow_duel` just
    stops, `winner=None`); Temper's effect on Melee (this project has no
    `Temper` model anywhere at all, not merely an unwired mechanic); and
    Victory/Death's aftermath ([5.9]) -- looting, magic items changing
    hands, and a slain King's heir taking over with *player-chosen*
    starting ability levels, which needs an interactive choice channel
    this automated engine has none of.
  - Non-breaking: brand-new, self-contained module with no existing
    callers -- full suite passed unchanged (900 passed) before any new
    tests were written. 15 new tests added (915 passed total).
- **Phase 49**: wires Phase 48's Encounter core into the Duel
  ([7.1]), the first of its four flagged consumers (Search, Challenge/
  Pursue, ASpy/Defend, Duel) to actually connect to it. Replaces
  `estimate_win_probability`'s strength-ratio approximation with a real
  `resolve_melee_duel` fight between the two Supreme Commanders --
  **opt-in only** (`use_real_duel_combat: bool = False` on
  `fight_battle()`/`_maybe_fight_duel`), the same pattern Phase 35 used
  for fanaticism: a real personal-combat resolution consumes a
  variable, not-knowable-in-advance number of `rng.random()` calls
  (until someone's hit points reach 0), which would silently desync
  every existing scripted-`rng` test sequence in this project if turned
  on unconditionally.
  - **`_commander_combatant(commander, state)`** (new): builds an
    `encounter.Combatant` for a Supreme Commander -- real
    `Ability.MELEE` skill from `LeaderState.skills` (0 if unrecorded,
    the same placeholder convention used everywhere else in this
    project), `CHARACTER_HIT_POINTS` (10), and the Neutral Kingdom
    "Order of Duelists" +1 bonus ([5.0]) read from `KingdomState.
    alignment`. The provincial garrison commander (`leader_id=None`,
    "has no abilities") gets Melee skill 0 and no bonus -- no real
    character exists to look either one up for.
  - **Always Melee, never Fire Arrow**: no Encounter Plan data exists
    anywhere in this project to know which tactic a commander would
    actually choose, and Melee needs no skill prerequisite ("You can
    enter melee even if you have no skill in melee combat") -- the one
    defensible default, a documented design choice.
  - **Critical distinction preserved**: rulebook [7.1] only says "the
    armies which were led by the loser of the duel will become
    demoralized" -- it never says the losing *commander* dies, unlike
    personal combat's own generic rule ([5.0]: "until one combatant is
    killed"). `_maybe_fight_duel` reads only `resolve_melee_duel`'s
    `winner` field and otherwise ignores the resolved hit-point state --
    the losing commander's own `LeaderState` is left completely
    untouched, only his side's `BattleUnit`s are demoralized, exactly as
    before. A dedicated test confirms the loser is never removed from
    `state.leaders`.
  - **The astronomically-unlikely "no decisive winner" edge case**
    (`resolve_melee_duel`'s own defensive round cap exhausted with
    neither combatant "dead," effectively impossible at 10 hit points
    each) is treated as no duel having occurred at all
    (`loser_side=None`) -- an explicit, documented fallback, not left to
    crash or guessed at.
  - Non-breaking: full suite passed unchanged (915 passed) immediately
    after wiring, before any new tests were written -- the opt-in
    default means every pre-existing test (all of which omit
    `use_real_duel_combat`) is byte-for-byte unaffected. 8 new tests
    added (923 passed total).
- **Phase 50**: `turn/challenge_execution.py`, the first
  Challenge (`ActionCode.CHALLENGE`, rulebook [3.12] "Encounter
  Character" -- naming mismatch confirmed in `turn/
  challenge_pursue_decode.py`) resolver -- encounter-acceptance rules
  plus real combat, reusing Phase 48's Encounter core the same way
  Phase 49's Duel wiring did.
  - **`is_encounter_accepted`** implements [3.12]'s decision tree
    directly, quoted in full in the module docstring: a King target
    only accepts a non-peaceful encounter if `mutual_encounter` (both
    King and challenger ordered a Challenge on each other, same
    province, same phase); a Hero leading an army never accepts; an
    armyless Hero challenged by a King evades 50% of the time
    (`rng.random() < 0.5`); an armyless Hero challenged by another Hero
    always accepts. Every branch has a concrete rulebook percentage or
    rule -- no guessing needed.
  - **`has_combat_intent`** checks the already-decoded
    `ChallengeRequest.tactics` for `Maneuver.MELEE`/`Maneuver.SHOOT` --
    "If the encounter plan has no combat tactics... these restrictions
    do not apply" ([3.12]) -- a peaceful plan bypasses the entire
    acceptance check and always succeeds without combat. Steal and
    Cast's own "personal combat spells (including Charm)" nuance is
    *not* checked (documented narrowing: Steal is unmodeled per
    `turn/encounter.py`'s own scope, and classifying which spells count
    as personal-combat needs a spell-effect system this project
    doesn't have).
  - **`execute_challenge(state, challenger_leader_id, request, rng,
    *, mutual_encounter=False)`**: co-location check (Encounter requires
    "the same province"), target-not-found handling, acceptance check
    (skipped entirely for peaceful plans), and -- if accepted with
    combat intent -- a real `resolve_melee_duel` between the two
    leaders (always Melee, same documented default as Phase 49's Duel
    wiring, for the same reason: no Encounter Plan tactic-choice data
    exists to pick Fire Arrow instead). A decisive loser is removed
    from `state` via `GameState.remove_leader()`.
  - **Unlike Duel's own [7.1] special case (Phase 49), a Challenge
    loser *is* killed**: personal combat's generic rule ([5.0]: "until
    one combatant is killed") applies here in full. Duel's
    "demoralizes armies, never kills the commander" rule is specific to
    [7.1] and does not generalize to every kind of Encounter -- each
    consumer of `turn/encounter.py`'s combat core has to re-derive its
    own death-or-not rule from its own rulebook section, not assume the
    other consumer's rule applies.
  - **`mutual_encounter` is caller-supplied only, not auto-detected**:
    knowing whether the target King also ordered a Challenge back needs
    visibility into another leader's own order, which `turn/
    plan_dispatch.py`'s single-leader dispatch doesn't have -- the same
    structural gap `turn/turn_processor.py` (Phase 45) exists to close.
    `execute_challenge` defaults it to `False` (a King target is never
    wrongly accepted when the caller can't actually confirm mutuality);
    wiring real mutual-encounter detection into `run_turn()` is a
    natural follow-up, not attempted this phase.
  - **Not wired into `plan_dispatch.py`'s CHALLENGE dispatch**, which
    stays decode-only exactly as it was -- same "built but not
    auto-invoked" precedent as `fight_multi_attacker_battle` (Phase 28)
    and `execute_practice_group` (Phase 46): `mutual_encounter` can't be
    determined from a single-leader dispatch, and real combat's
    variable rng consumption would perturb this project's existing
    scripted-`rng` test sequences if wired in as the unconditional
    default.
  - Rulebook [4.33]'s Spy Table (Pursue/Trail's own catch-up-chance
    formula) is a related, natural follow-up -- not attempted this
    phase; Pursue's own acceptance-and-combat resolver stays unbuilt.
  - Non-breaking: brand-new, self-contained module with no existing
    callers -- full suite passed unchanged (923 passed) before any new
    tests were written. 18 new tests added (941 passed total).
- **Phase 51**: `turn/spy_table.py` (rulebook [4.33] Spy
  Table's catch-up formula) plus `turn/pursue_execution.py`, a
  **single-phase-only** Pursue ([3.16]) resolver -- scoped down from a
  full persistent multi-phase chase, confirmed with the user before
  implementation (see the task list: "Spy Table + cattura in singola
  fase" over the full multi-phase/army-battle alternative).
  - **`pursue_catch_up_chance`** implements [4.33]'s table exactly as
    quoted in the module docstring: base % by Spy skill level 0-4
    (50/100/150/200/250%), x2 if the target leads an army, divided by
    distance in provinces, 100% if pursuer and target share a Kingdom
    -- clamped to [0, 1] (the raw formula can exceed 100%, e.g. a
    level-4 Spy chasing an army-leading target at distance 1 is 500%).
    Only the table's third column is modeled; "Chance of Escaping
    Notice" and "Margin of Error of Spy Reports" belong to ASpy
    ([3.14]), which has no resolver in this project yet (`turn/
    aspy_defend_decode.py` is decode-only) -- left unimplemented rather
    than guessed at partial relevance.
  - **Distance-0 special case, a documented design choice, not a
    rulebook quote**: the table's own "divided by distance" is
    undefined at distance 0 (same province). Treated as guaranteed
    catch-up, the same way the table's own "same Kingdom -> 100%"
    carve-out already treats a different full-certainty case.
  - **`turn/movement.py hex_distance`** (new): straight-line hex
    distance between two `HexCoord`s, via the standard odd-r-to-cube
    coordinate conversion -- verified before use to reproduce exactly
    the module's existing 6-neighbor adjacency (`neighbors`/
    `is_adjacent`) at distance 1, for both even and odd rows. Not a
    pathfinding distance: unlike Move's own "through friendly hexes if
    possible" chase algorithm ([3.1], still unimplemented), the Spy
    Table's "distance (in number of provinces)" carries no pathfinding
    rule, so this ignores terrain, ownership, and unexplored hexes.
  - **`execute_pursue`** resolves [3.16]'s own army-leading-match check
    first ("If the Pursuing character leads an army and the pursued
    character doesn't, or visa versa, the Pursue order is ignored"),
    then rolls the Spy Table catch-up chance for the current phase
    only. If both sides lead armies and the pursuer catches up, the
    result reports `caught_up=True` with an explicit
    `reason="army-vs-army pursuit battle not modeled"` and fights
    nothing -- wiring `fight_battle` in for this case is a declared,
    explicit follow-up, not attempted here (it needs `BattleUnit`s
    built from each side's real armies, more orchestration than this
    phase's scope). If neither side leads an army and the pursuer
    catches up, **"All rules listed under the Encounter action apply to
    Pursuit encounters" ([3.16]) is read literally**: the caught-up
    target goes through Phase 50's exact same `has_combat_intent`/
    `is_encounter_accepted`/`resolve_melee_duel` pipeline, including a
    King target's own `mutual_encounter` requirement (caller-supplied
    only, defaulting to `False`, same conservative choice as Phase 50).
    A decisive loser is removed from `state` via `remove_leader()`.
  - **Explicitly single-phase, not the persistent "for the rest of the
    turn" chase the rulebook describes**: tracking a Pursue order's
    state *across* phases needs the same cross-phase, cross-leader
    visibility `turn/turn_processor.py` (Phase 45) exists to provide --
    a natural follow-up, not attempted this phase. `execute_pursue`
    only answers "does the pursuer catch up *this* phase, and if so
    what happens."
  - **Not wired into `plan_dispatch.py`'s PURSUE dispatch**, which stays
    decode-only exactly as it was -- same "built but not auto-invoked"
    precedent as Challenge (Phase 50) and the others before it.
  - Trail's own resolver (also driven by the Spy Table's "Chance to
    Pursue or Trail" column, per [4.33]'s own note) remains unbuilt --
    a natural follow-up now that `pursue_catch_up_chance` exists to
    reuse.
  - Non-breaking: `hex_distance` is a pure addition to `turn/
    movement.py` with no existing callers touching it, and `turn/
    spy_table.py`/`turn/pursue_execution.py` are brand-new,
    self-contained modules -- full suite passed unchanged (941 passed)
    before any new tests were written. 34 new tests added (1334 passed
    total; the jump is mostly `hex_distance`'s own neighbor-adjacency
    test, parametrized across the whole map like `test_movement.py`'s
    existing adjacency-symmetry test).
- **Phase 52**: `turn/trail_execution.py`, a single-phase
  Trail ([3.17]) resolver -- the natural, small follow-up flagged at
  the end of Phase 51, since [4.33]'s Spy Table "Chance to Pursue **or
  Trail**" column is one shared formula and `turn/spy_table.py`
  already existed to reuse.
  - **`execute_trail`** validates [3.17]'s own restriction ("A
    character leading an army may not be ordered to Trail" -- the
    order is ignored, reported via `reason`, not raised as an
    exception, the same convention Pursue's army-leading-mismatch rule
    uses), then rolls the same `pursue_catch_up_chance` Pursue uses
    (Phase 51), driven by the trailer's real `Ability.SPY` skill,
    whether the target leads an army, distance via `hex_distance`, and
    same-Kingdom status. Unlike Pursue, there is no "both sides must
    lead an army or neither" symmetry rule -- only the trailer's own
    army-leading status is restricted.
  - **Deliberately no intelligence payload, a documented scope
    decision, not an oversight**: `TrailExecutionResult` only reports
    `spied_on: bool`, not the rulebook's own "Actions, race, temper,
    alignment, treasures owned and armies led" (or, for a King, "
    finances, alliances, enemies and controlled provinces"). Two
    already-declared project-wide gaps, not new ones invented here:
    this project has no report-generation system at all yet (same gap
    ASpy's own note already flags), and several of those named fields
    -- race, temper, alignment, per-leader treasure ownership -- don't
    exist anywhere in `LeaderState` to report on regardless (`Temper`
    has no model in this project at all, confirmed back in Phase 48's
    own `turn/encounter.py` docstring). A future report-generation
    phase is the natural place to extend this, once those fields
    exist.
  - **Not wired into `plan_dispatch.py`'s TRAIL dispatch**, which stays
    decode-only -- same "built but not auto-invoked" precedent as
    every other action resolver in this project.
  - ~~**Trail's remaining gap** (see Phase 27's note above)~~ -- closed
    for the catch-up-resolution piece; the intelligence-payload piece
    stays open pending report generation, as explained above.
  - Non-breaking: brand-new, self-contained module with no existing
    callers -- full suite passed unchanged (1334 passed) before any new
    tests were written. 8 new tests added (1342 passed total).
- **Phase 53**: wires a real army battle into `turn/
  pursue_execution.py`'s army-vs-army catch-up case, closing the
  explicit gap Phase 51 declared (and flagged as its own natural
  follow-up).
  - **`_fight_army_pursuit_battle`** relocates the pursuer's leader and
    every army they command to the target's location, then calls
    `turn/battle_orchestrator.py fight_battle` there.
    **Relocation-on-catch-up is a documented design choice, not a
    rulebook quote**: this project's single-phase abstraction (Phase
    51) has no multi-province chase path to walk the pursuer's armies
    along, so "catches up" is modeled as the pursuer's whole force
    converging on the target's province the instant the Spy Table roll
    succeeds -- the same abstraction level already used for the
    armyless case's encounter (no travel time modeled there either).
  - **Two narrow, explicitly-guarded carve-outs**, both falling back to
    `caught_up=True` with a `reason` instead of fighting: a pursuer
    with no Kingdom (`fight_battle` needs a concrete
    `attacker_kingdom_id`; an independent Hero leading an army has
    none) and a target location with no `ProvinceState` recorded
    (`fight_battle` needs terrain/ownership data that doesn't exist for
    an unexplored or out-of-map hex).
  - `PursueExecutionResult` gains a `battle_report: BattleReport | None`
    field, surfacing `fight_battle`'s own full result (quality changes,
    retreats, conquest, duel outcome if any) directly -- no new
    battle-result shape invented, the same `BattleReport` every other
    `fight_battle` caller already returns.
  - **Multi-phase persistent chase state remains the one open gap**:
    `execute_pursue` still only resolves a single phase's catch-up-and-
    battle; the rulebook's "for the rest of the turn" standing order
    still needs `turn/turn_processor.py` integration, not attempted
    here.
  - Non-breaking: `fight_battle` is an existing, already-tested
    function reused as-is (not modified) -- full suite passed unchanged
    (1342 passed) before any new tests were written. 2 net new tests
    added (one old placeholder test replaced by three narrower ones;
    1344 passed total).
- **Phase 54**: `turn/plan_dispatch.py`'s CHALLENGE, PURSUE,
  and TRAIL dispatch now call `execute_challenge`/`execute_pursue`/
  `execute_trail` (Phases 50-53) directly, replacing their previous
  decode-only dispatch (`decode_challenge_phase`/`decode_pursue_phase`/
  `decode_trail_phase` alone) -- the "built but not auto-invoked" gap
  flagged repeatedly across those three phases is now closed for the
  single-leader dispatch path.
  - **`mutual_encounter` defaults to `False` at this dispatch layer**,
    the same documented conservative choice already established in
    Phases 50/51: a King target is never wrongly accepted when the
    caller can't actually confirm the target King also ordered a
    Challenge/Pursue back. Detecting a *real* mutual pair -- two
    leaders targeting each other with Challenge/Pursue in the same
    phase -- needs the same cross-leader, same-phase visibility
    Multiple Contingents and Practice's own multi-character
    coordination needed (`turn/turn_processor.py`, Phases 45/46).
    **This was scoped down deliberately, confirmed with the user
    before implementation** (task list: "Solo dispatch a singolo
    leader" over the larger "dispatch + rilevamento cross-leader
    reciproco" alternative) -- wiring that detection into
    `turn_processor.py` is a declared, natural follow-up, not this
    phase's own scope.
  - No changes to `turn/challenge_execution.py`, `turn/
    pursue_execution.py`, or `turn/trail_execution.py` themselves --
    this phase is pure wiring, three new one-line-body wrapper
    functions (`_dispatch_challenge`/`_dispatch_pursue`/
    `_dispatch_trail`) mirroring the existing `_dispatch_cast`/
    `_dispatch_practice` pattern.
  - Three pre-existing "is decode only" tests legitimately changed
    behavior and were updated (not just re-asserted) to reflect real
    execution; one new test (`test_dispatch_challenge_executes_a_real_
    encounter_when_target_exists`) confirms a full real encounter now
    runs end-to-end through `dispatch_phase`.
  - Non-breaking in the sense that every other action's dispatch is
    untouched; CHALLENGE/PURSUE/TRAIL's own behavior deliberately
    changed (decode-only to real execution) as this phase's whole
    point -- full suite passed with only the three anticipated,
    already-updated test failures before the fix, then 1345 passed
    total after (net +1 over Phase 53's 1344: three old tests replaced
    by four new ones).
- **Phase 55**: wires `turn/contested_province.py`'s
  forced-rebattle rule ([7.6]) into `turn/turn_processor.py`, closing
  the module's own "fast follow-up, not attempted yet" note left open
  since Phase 45.
  - **`_dispatch_contested_rebattles`** runs once at every phase
    boundary (before phase index 1-4, i.e. "the next phase" after any
    phase whose battle could have left a province contested), scanning
    every `ProvinceState` with `contested_by_kingdom_id` set. If the
    contesting kingdom's armies there still each have >=1 movement
    point (`attacker_can_force_rebattle`, already built in Phase 5) and
    a non-allied defender remains, it calls `fight_battle` again
    automatically -- not tied to any leader's own `PlanPhase` that
    phase -- then deducts `contested_battle_movement_cost(conquered=...)`
    (1 point, or 2 if this rebattle conquers the province) from each
    attacking army, quoting [7.6] exactly: "your armies will use up a
    movement point to fight a battle... If the province is conquered,
    the attacker uses another movement point."
  - **A province stops auto-rebattling the moment movement points run
    out** ("both armies will encamp") -- simply not being checked again
    successfully on the next boundary; no separate "encamped" flag
    needs to exist anywhere, `fight_battle`'s own contested-flag
    bookkeeping (already correct since Phase 9) does the rest.
  - **Cross-turn carryover is a documented scope boundary, not an
    oversight**: the rulebook separately describes a contested province
    still active "at the start of the next gameturn['s phase 1]" -- this
    project has no multi-turn/season loop (`run_turn()` only ever
    processes one turn's P0-P4 per call), so that case can't be
    distinguished here from an ordinary same-turn continuation; both
    are handled identically by the same boundary check.
  - The forced rebattle's own result is appended to `run_turn`'s
    returned list as a `PhaseDispatchResult` with `phase_label=
    "forced-rebattle"`, `segment_index=-1` (a sentinel -- it isn't tied
    to any leader's own plan segment, same category as the existing
    `_dispatch_single` wrapper's own segment-index sentinel), and
    `leader_id` read from the battle's own `attacker_commander_leader_id`
    (falling back to `0` if the attacking side somehow has no
    identifiable commander).
  - Non-breaking: the new check is a no-op whenever no province is
    contested, which is every existing test's own starting state --
    full suite passed unchanged (1345 passed) before any new tests were
    written. 5 new tests added (1350 passed total).
- **Phase 56**: wires mutual Challenge/Pursue detection into
  `turn/turn_processor.py`, closing the declared follow-up flagged when
  real Challenge/Pursue execution was wired into `plan_dispatch.py`
  (Phase 54): "detecting a real mutual pair... needs the same
  cross-leader, same-phase visibility Multiple Contingents and
  Practice's own multi-character coordination needed."
  - **Detection**: when leader A's CHALLENGE or PURSUE phase at a given
    label targets leader B, and B's own CHALLENGE or PURSUE phase at
    that *same* label targets A back, the pair is routed through the
    new `_dispatch_mutual_encounter` instead of each dispatching solo.
    `phase.obj` is read directly as the target character id -- no
    decode call needed for detection itself, since `ChallengeRequest`/
    `PursueRequest` already confirmed `obj` *is* the target id (Phase
    25). A leader Pursuing their own id ([3.16] "Patrol") is explicitly
    excluded from ever matching itself as a mutual pair.
  - **Single shared resolution, confirmed with the user before
    implementation** (task list: "Un solo scontro condiviso" over the
    "due scontri separati" alternative): the rulebook only ever
    describes *one* encounter resulting from mutual orders, and
    resolving two independent duels between the same pair risked a
    second duel against a combatant the first one already killed. Both
    leaders' `PhaseDispatchResult` entries share the exact same result
    object.
  - **King-target initiator rule, a documented design choice**: if
    exactly one of the two leaders is a King, that King is always
    treated as the *target* (never the challenger) when calling
    `execute_challenge`/`execute_pursue` -- [3.12]'s `mutual_encounter`
    mechanism exists specifically to override a King *target's*
    acceptance, so the King has to occupy that role for the rule to
    mean anything; picking the King as challenger instead would
    silently route a King-vs-armyless-Hero pair through the wrong
    branch of `is_encounter_accepted` (a 50% evasion roll instead of
    guaranteed acceptance) -- confirmed by a dedicated test using a
    King with a numerically *lower* `leader_id` than the Hero, so a
    naive "lower id is always challenger" tiebreak would have gotten it
    wrong. If both or neither leader is a King, the choice is otherwise
    symmetric for the King-acceptance branch, so the lower `leader_id`
    is used as challenger purely as a deterministic tiebreak -- an
    unsourced simplification for a case the rulebook doesn't
    disambiguate (it can still affect a non-King Challenge's own
    target-leads-an-army check), not a claim about the "correct"
    real-game resolution.
  - **The initiator's own action type governs which resolver runs**
    (Challenge or Pursue); the other leader's own tactics/Encounter
    Plan aren't modeled separately in the shared resolution -- a
    documented simplification, not a claim that mixed Challenge+Pursue
    mutual pairs are fully modeled from both sides.
  - Non-breaking: the new detection only activates for two same-phase
    CHALLENGE/PURSUE orders that target each other, which no existing
    test's fixtures produce -- full suite passed unchanged (1350
    passed) before any new tests were written. 4 new tests added (1354
    passed total).
- **Phase 57**: wires Defend's [3.15] reactive
  battle-joining into `turn/turn_processor.py`, via a new `turn/
  defend_execution.py`.
  - **A confirmed blocker forced a scope pivot mid-implementation**:
    ADDEND.AK's own corrected coverage formula ("adjacent to both the
    named province and the province the leader is currently located
    in") needs the Defend order's own named-province target as a real
    `HexCoord` -- but `DefendRequest.target_province` is kept as a raw,
    unconverted int (`turn/aspy_defend_decode.py`, Phase 26), because no
    confirmed numbering scheme exists for ASpy/Defend's province
    references at all (LMOVE's own `hex_numbering.py` scheme is itself
    only an empirically-inferred guess with no confirmation it applies
    to ASpy/Defend's `obj` field too). Converting it would have stacked
    one unconfirmed mapping on top of another. **Confirmed with the
    user**: rather than leaving Defend blocked like Use_MI, coverage is
    approximated as every province adjacent to the general's own
    current location alone (`defend_coverage_area`) -- a documented,
    conservative *superset* of the true addendum area (intersecting two
    neighbor-sets can only shrink or preserve a set, never expand it),
    so this may react to an invasion the real narrower rule wouldn't
    have covered, but never misses one it would have.
  - **`_apply_defend_reinforcements`** relocates a covering Defender's
    leader and every army they command to an invaded, covered,
    friendly-owned province -- the same relocate-then-fight abstraction
    already used for Pursue's own army-vs-army catch-up (Phase 53) and
    the contested-province rebattle (Phase 55) -- so the existing
    battle-dispatch machinery (solo `execute_move` or Multiple
    Contingents) picks the reinforcement up as a real defender
    automatically, even when the invaded province had zero standing
    defenders beforehand (`move_execution.py`'s own `occupied_by_enemy`
    check needs a defender physically present *before* it evaluates).
  - **A Defend order activates starting the *next* phase, not the one
    it's given in** -- a documented simplification sidestepping the
    Italian rulebook's own noted-but-unmodeled "Defend always resolves
    last in its phase" ordering nuance (flagged back in `turn/
    aspy_defend_decode.py`'s own docstring) rather than inventing
    same-phase ordering semantics this project has no other precedent
    for.
  - **Consumed after its first reinforcement this `run_turn()` call**:
    once a Defending general commits to one battle, they're no longer
    standing by to cover their original area for a second, unrelated
    invasion later in the same turn -- a documented, unsourced
    simplification (the rulebook doesn't address reinforcing twice).
  - **No movement-point cost modeled for the reactive move itself** --
    unlike the contested-province rebattle's explicit "will use up a
    movement point" text, [3.15] never says a Defend reaction costs
    anything.
  - Only reinforces **friendly-owned ground** (the invaded province's
    owner is the Defender's own Kingdom or an ally) against a
    **non-allied invader who actually brings an army**.
  - ~~**ASpy/Defend's remaining gap** (see Phase 26's note above):
    both need game-state logic not present anywhere in the available
    Pascal source~~ -- **Defend's own reactive battle-joining is now
    implemented** (this phase). **ASpy's own report-generation gap
    stays fully open**: intelligence-report content still needs a
    report-generation system this project doesn't have at all, a much
    larger and structurally different piece than Defend's own
    coverage-and-reinforcement mechanic turned out to be.
  - Non-breaking: brand-new module plus additive `run_turn()` logic
    that only activates when a DEFEND order was actually given -- full
    suite passed unchanged (1354 passed) before any new tests were
    written. 7 new tests added (3 for `defend_coverage_area` itself, 4
    for the `run_turn()` wiring; 1361 passed total).
- **Phase 58**: begins report generation -- the "structurally
  biggest piece remaining" flagged at the end of Phase 57 -- with a new
  `report/` subpackage and its first module, `report/prose.py`, a
  micro-template rendering engine. **Explicitly the foundation, not any
  report content yet**: this module renders one already-selected
  template string given substitution values; it knows nothing about
  `GameState`, the same separation Phase 48's Encounter core established
  before any of its consumers existed.
  - **Research materially changed the size/risk estimate before any
    code was written, and was reported back to the user before
    proceeding**: `HostAK/TP/SAY.PAS`/`RUMORS.PAS` (~4000 combined lines,
    115 procedures) and the `HostAK/TP/PROSE/` folder (164 `.X`/`.X2`
    template files) turned out to contain the *actual* English sentence
    templates as real, quotable text -- not just opaque binary logic --
    and `HostAK/TP/PROSE/PROSE.TXT` documents the template
    mini-language's symbols in full (written for a translator, but a
    complete spec nonetheless). This is real, sourced content, not
    something to invent. The genuinely large, still-unbuilt part is
    `RUMORS.PAS Say()`'s own stateful narrator engine: 1st/2nd/3rd-person
    narration depending on who's reading, gender-based pronoun
    selection, "already mentioned this character" sentence-merging
    (turning two events into "recruited 222 and 223"), and King-only
    exclusion zones -- confirmed by reading `Set_Person`/`Set_Alt`/
    `Set_Plural`'s real implementations, not guessed at.
  - **`render(template, values, *, rng)`** implements exactly the
    symbols `PROSE.TXT` documents that are also confirmed, from
    `Say_Options`'s real source, to be genuinely random: `_` (space),
    `{...}` (50% inclusion), `/R` (50/50 word choice), plain
    caller-supplied placeholder substitution, and `^A` (a/an, resolved
    by peeking past the substituted text to the next real word). The
    staged resolution order (`/R` before `{...}` before `_`-to-space)
    is copied directly from `Say_Options`'s own procedure body, not
    inferred from the prose description alone -- `/R`'s word-boundary
    scan depends on `_` still being literal at that point (an
    underscore-joined phrase like `bored_with` counts as one word).
  - ~~`/F`, `/S`, `/P` raise `NotImplementedError` naming the exact
    marker instead of being silently treated as another random 50/50
    choice**: confirmed from `Say_Options`'s `Left_Choice` function that
    none of the three is actually random at the Pascal level (`/F`
    reads a feature-instance parity bit, `/S` reads sea-vs-land terrain,
    `/P` reads a sentence-merge state flag) -- this project has no
    per-render-call source for any of that context yet~~ -- **`/S` is
    implemented as of Phase 74 and `/F` as of Phase 76** (see those
    phases' own notes below); each still defaults to raising rather
    than guessing wherever this project genuinely lacks the needed
    context (`/S`/`/F` themselves now take that context as a caller
    parameter instead). **`/P` alone still raises
    `NotImplementedError`**: confirmed from `Say_Options`'s own
    `Left_Choice` function that it reads a sentence-merge state flag
    (`mlist`) this project has no per-render-call source for yet, and
    guessing a random substitute would be quietly wrong in a specific,
    checkable way, worse than an honest "not yet."
  - **Full pronoun/narrator logic (`<`, `[`, `>`, `]`, `^B`/`^E`) is a
    declared, separate follow-up**, not attempted this phase -- it needs
    `Set_Person`/`Set_Alt`'s own stateful person/gender/repeat-tracking
    system, a genuinely different and larger piece of work than a
    stateless template renderer.
  - Validated against real quoted template strings from `RUMORS.PAS`
    (cited by line number in the test file), including an end-to-end
    render of `_LPOwns` (line 446) that reproduces, word-for-word, the
    exact phrasing found in the real sample report `SE3__T0.K1`: "The
    province of the Dolphin Sea owes allegiance to your Majesty."
  - **Roadmap for the phases after this one** (not committed to exact
    numbering): a "story event" model recording what happened during
    `ak_engine`'s own already-computed turn results (battles, moves,
    casts, recruits...); then `Set_Person`/`Set_Alt`'s narrator system;
    then individual report sections wired one at a time (Quote of the
    Week first, since `PROSE/QUOTES.X2` needs no game-state at all;
    then FINANCES/PROVINCES/CHARACTERS/ARMIES, which are structured data
    this project already computes; the full narrative ACTION REPORT and
    birthright-report province descriptions last, since they need the
    most of the deferred narrator machinery) -- validated turn-by-turn
    against the real `SE3__T*.K1` sample reports as they become
    available.
  - Non-breaking: brand-new subpackage with no existing callers -- full
    suite passed unchanged (1361 passed) before any new tests were
    written. 19 new tests added (1380 passed total).
- **Phase 59**: executes 10 of the 13 real spells Phase 29 left
  unmodeled (Resurrect, Part Sea, Bless, Flood, Tornado, Earthquake,
  Oratory, Plague, Illusory Terrain, Phantasmal Armies), unblocked by
  **`Regolamento AK.txt`**, a more detailed Italian-language rulebook the
  user supplied and asked to be studied specifically for its spell
  mechanics -- it spells out exact percentages, damage ranges, and
  targeting rules the English `RULES.AK`/`ADDEND.AK` sources never gave
  (Phase 29's own docstring named this gap explicitly for exactly these
  ten spells). The `.doc` was converted with `antiword -m UTF-8.txt` and
  committed to the repo root as a plain-text, greppable, directly
  quotable source (`../Regolamento AK.txt`, outside this package).
  - **Research first identified the real remaining scope, then the user
    confirmed proceeding with all of it in one phase**: of the 23
    unmodeled spells, 10 are Personal-Combat-only ([5.1]: Holy Symbol,
    Spiritwrack, Psychic Blast, Telekinetic Storm, Invisibility, Mirror
    Image Phantasm, Fireball, Ice Suspension, Hand of Death, Control
    Undead) and can never be cast via a top-level `ActionCode.CAST`
    phase at all (confirmed by `cast_decode.py`'s own validation against
    all 108 real sample Cast phases: only Action spells ever appear
    there) -- they only exist inside an encounter's own tactic list, and
    `turn/encounter.py`'s own docstring already scopes out the general
    tactic-sequence combat engine (range transitions, mixed tactics, a
    monster-HP model, spell effects mid-combat) they'd need. Of the
    remaining 13 Action spells, Skeletal_Army needs a per-province
    "who died here" registry no battle-resolution code populates,
    Hide_Feature needs the still-unpopulated `Feature` stub
    (~~stub~~ **a real `Feature`/`FeatureType` model exists as of Phase
    75**, but there's still no way to populate a game's actual feature
    roster -- world generation -- so Hide_Feature stays blocked), and
    Clairvoyance needs the "story event" model Phase 58's own roadmap
    already deferred -- all three stay unexecuted for the same reason
    Resurrection was blocked before this phase: real, structural gaps,
    not oversights. The other 10 had no such blocker once the numbers
    existed, so this phase implements all 10 together rather than
    splitting them further.
  - **`GameState.dead_leaders`** (new): `remove_leader()` now archives
    into it instead of discarding, giving Resurrection something
    concrete to revive from -- the exact gap Phase 29's docstring named.
    Only the ordinary-Hero case is modeled; the rulebook's separate
    King-via-Heir revival (Heir must have zero Talents assigned; a
    revived King resumes his own throne rather than joining the
    reviver's Kingdom) needs a throne/heir-succession model this project
    doesn't have. A successful Resurrection now also dispatches its
    target's own embedded plan the same turn, the same as a successful
    Charm always has (`plan_dispatch.py _nested_plan_triggered`).
  - **Province-targeted spells share one targeting mechanism**
    (`cast_execution._resolve_province_target`): `CastRequest.target`
    decodes via `turn/hex_numbering.py`'s already-existing,
    empirically-derived scheme (Phase 11 -- not 100% validated, see that
    module's own docstring), reusing `board_width` the same way Move's
    own LMOVE decoding already does (`execute_cast` gained an optional
    `board_width` parameter, threaded through
    `plan_dispatch._dispatch_cast`). Each spell enforces its own
    same-province-or-adjacent rule, except Bless, which the rulebook
    explicitly exempts ("any province on the map, regardless of where
    the caster is").
  - **Three new `ProvinceState` fields are set but have no consumer
    yet**, an intentional "spell writes real state, a later phase makes
    the rest of the engine honor it" split, the same shape Phase 55 used
    for `contested_by_kingdom_id` before its own rebattle logic existed:
    `terrain_override` (Part Sea: Sea->Plains; Flood: non-mountain
    land->Sea -- Flood's secondary "land units trapped" effect stays
    unmodeled, since this project has no first-class land-vs-sea unit
    classification), `tax_modifier_percent` (Bless +60%, Earthquake
    -100%, both "not cumulative" so each *sets* rather than adds --
    genuinely no consumer at all yet, since no tax/revenue-collection
    system exists anywhere in this project), and `illusory_terrain`
    (Illusory Terrain's fake-terrain record -- the dissolve-chance timer
    and blended real/illusory combat strength both need
    exploration/movement-side consumers that don't exist).
  - **Tornado and Plague are the two spells with a real, immediate,
    stochastic effect**: every army in the target province gets an
    independent per-unit destroy roll (`TORNADO_DESTROY_CHANCE_PER_LEVEL`
    10%/level, no ownership exemption -- the rulebook explicitly says
    own/allied units aren't spared; Plague's `10% + 10%/level`, filtered
    to `HUMANOID_RACES` only, mercenary armies skipped since this
    project has no way to know an ownerless army's race). Plague's own
    "15%/phase spread to an adjacent province" stays unmodeled -- it
    needs the same per-phase scheduling `turn_processor.py` already uses
    for Defend's reinforcement (Phase 57), a natural follow-up.
  - **Oratory is applied as a direct, persistent `ArmyState.quality`
    bump** (capped at Elite), not a `strength.py` multiplier -- the
    rulebook literally describes it as units *becoming* Average/Veteran/
    etc., the same discrete step `Quality`'s own enum ordering already
    represents, more faithful than threading a fourth "SKIPPED" note
    through the strength pipeline. A new `LeaderState.
    oratory_boosted_this_turn` flag makes a second cast on the same
    leader the same turn correctly a no-op ("not cumulative") instead of
    double-bumping.
  - **Phantasmal Armies is a real `strength.py` multiplier**, the one
    spell in this batch with a natural, already-multiplicative extension
    point: `phantasmal_armies_multiplier` (+15%/level) joins
    `compute_effective_strength`'s existing chain (`combat_ability_
    multiplier`'s neighbor), and `LeaderState.phantasmal_armies_level`
    is threaded through `battle_orchestrator._build_battle_units` the
    same per-army-commander-lookup pattern Druidic shortfall (Phase 41)
    already established. Unlike Druidic ability, an unled army gets no
    substitute source for this bonus -- the rulebook gives no
    garrison-commander fallback for it.
  - **Level-dependent magnitudes with no recorded caster skill** default
    to 0 (no effect), the same "no data -> no numeric effect" convention
    `compute_druidic_shortfall` already uses, not a guessed level.
  - Non-breaking: full suite passed unchanged (1380 passed) before any
    new tests were written (two pre-existing tests needed comment/name
    updates, not behavior changes, since Resurrection and Phantasmal
    Armies moved from "representative of an unmodeled spell" to "a real
    spell with its own specific unexecuted edge case"). 30 new tests
    added (1410 passed total): 26 in `test_cast_execution.py` (one or
    more per new spell, covering both the success path and each spell's
    own validation failures), 2 in `test_strength.py`
    (`phantasmal_armies_multiplier` + its `compute_effective_strength`
    integration), 2 in `test_battle_orchestrator.py` (the commander
    lookup + the unled-army no-bonus case).
- **Phase 60**: closes two of Phase 59's own deferred gaps --
  Skeletal_Army and Bless's corpse-cleanup addendum -- both of which
  turned out to need exactly the same missing piece: a per-province
  "what died here in a battle" registry. **The user asked directly
  whether these two `Regolamento AK.txt` "NUOVE REGOLE E MODIFICHE"
  additions (Bless's corpse-cleanup, Invisibility's +30% flee bonus) had
  been integrated in Phase 59** -- they hadn't, both for reasons already
  documented in Phase 59's own code (Bless's addendum explicitly named
  as unmodeled; Invisibility blocked along with every other
  Personal-Combat-only spell). The user then confirmed building the
  missing registry now, since it happened to unblock two spells for the
  price of one (Invisibility's own addendum stays blocked regardless --
  it needs the much bigger unbuilt combat-tactic engine, not this
  registry).
  - **`GameState.battle_graveyard`** (new): a `dict[HexCoord,
    list[GraveyardEntry]]`, each entry recording a destroyed army's
    `ArmyType`, `Quality` at death, and owning `kingdom_id` -- exactly
    what Skeletal Army's own rulebook text says matters ("identical in
    every way to the dead army"). Populated by
    `GameState.record_battle_death()`, called from all four of
    `turn/battle_orchestrator.py`'s real army-elimination sites
    (`_retreat_or_disband`'s no-retreat-destination disband,
    `_apply_pursuit`'s catch-and-destroy, and each side's own
    clean-swept elimination in `fight_battle`) -- and *only* those four:
    Tornado/Plague's own spell-caused kills (`turn/cast_execution.py`)
    are deliberately excluded, since the rulebook's own wording is
    specifically "battaglia" (battle), not any destruction.
  - **Bless's addendum executes**: after the base +60% tax effect
    applies, a second, independent roll (10%+10%/level in White Magic)
    decides whether the target province's graveyard is cleared outright
    -- "also removes," not "instead of," so a failed cleanup roll still
    leaves the tax bonus in place.
  - **Skeletal Army executes**: no target field (`cast_decode.py`'s
    `NO_TARGET_SPELLS`) -- operates on the caster's own current
    province. Raises `min(caster's Necromancy level, graveyard entries
    available)` new armies, each identical to a consumed graveyard entry
    (type and quality preserved, "no way to choose which type answers
    the call" honored by just popping arbitrary entries), joining the
    caster's own kingdom and command. An empty graveyard at the caster's
    location fails the spell outright *before* any success roll --
    "provided enough units died in battle" is a precondition, the same
    "check applicability first" order every Phase 59 spell already
    uses. **Deliberately not modeled**: "all its movement points" is
    approximated as the same `movement_points=0` every freshly-recruited
    army gets (no precedent anywhere in this project for carrying over
    an exact remaining-movement value across a unit's death), and the
    global 350-unit world cap plus its ~10%/turn decomposition are
    unenforced soft world-balance rules, not core mechanics.
  - Non-breaking: full suite passed unchanged (1410 passed) before any
    new tests were written (two pre-existing "representative unmodeled
    spell" tests were repointed from Skeletal_Army, now executed, to
    Hide_Feature, still blocked -- a comment/name fix, not a behavior
    change). 8 new tests added (1418 passed total): 1 new + 2 extended
    in `test_battle_orchestrator.py` (graveyard population across all
    three battle-death paths), 7 in `test_cast_execution.py` (3 for
    Bless's cleanup roll, 4 for Skeletal Army: raising, empty-graveyard
    failure, level-capped count, and the no-recorded-level fallback).
- **Phase 61**: `report/turn_report.py`, the first real consumer
  of Phase 58's `report/prose.py` rendering engine -- turns an
  already-computed `turn/battle_orchestrator.py BattleReport` into the
  same English battle-narrative sentences the original game's turn
  report contained. Scoped narrowly to the battle-outcome slice only
  (per-column clash, overall winner, destroyed/pursued/retreated
  armies) -- **not** the letter-report frame, financial report,
  exploration narrative, or feature discovery, which need `GameState`
  data this project doesn't track yet (character correspondence,
  treasury deltas, discovered features) or a turn-events log, a
  separate, much larger follow-up.
  - **Sourced from `HostAK/TP/SAY.PAS`'s `_BClash`/`_BRes`/`_BWinner`/
    `_BDie`/`_BPurs` dispatch table** (inside `Programma Pascal.zip`,
    around lines 1092-1139) and the real `HostAK/TP/PROSE/*.X` template
    files it names, not guessed. `_BClash` + `_BRes`: "`<army> fought
    with <army> and <result>`", where the per-column result is bucketed
    into 11 template files (MINUS5..MINUS1, ZERO, PLUS1..PLUS5) via
    `CASE bres OF -32000..-5: minus5; ... 5..32000: plus5`. **This
    project's archive has no surviving source for the formula that
    produces `bres` itself** -- only the case boundaries are confirmed
    -- so `margin_bucket()` derives an analogous margin from
    `BattleColumnResult.attacker_win_probability` (the same 0.0-1.0
    value `turn/battle_line.py estimate_win_probability` already
    computes for that column) instead of guessing at `bres`'s own
    scale, a documented, unsourced bucketing choice in the same style
    `turn/aftermath.py`'s constants already established. `_BWinner`
    picks WINNER.X on an attacker win, DEFWIN.X on a defender win; no
    template exists anywhere in the archive for a tie, so
    `render_battle_winner()` returns `None` rather than a guessed
    sentence. `_BDie`/`_BPurs` give the destroyed-army and
    pursuit-then-destroy sentences (KILLARMY.X, PURSUIT.X).
  - **Real templates are transcribed in `PROSE.TXT`'s own
    translator-facing notation (`^A`, `^S`, ...)**, the same convention
    `report/prose.py`'s own tests already use -- not the compiled
    `.X`/`.X2` files' raw single-byte control-character encoding.
    Inspecting the actual file bytes (not just a printed preview, which
    silently swallows control bytes) turned up a real discovery: Turbo
    Pascal's story files encode `^A` as a literal `chr(1)` byte, `^S` as
    `chr(19)`, etc. (`chr(1..26)` = "Ctrl + Nth letter"), confirmed
    against `PROSE.TXT` line 65 ("`^S`: Province name #2") and line 34
    ("`>`: first character possessive"). Converting that compiled
    encoding back to source notation is a one-time transcription step
    done here, not a runtime concern `prose.render()` needs to solve.
  - **`<`/`<2`/`<3`/`[`/`[1`/`[3` (character references) and `>`
    (possessive) stay caller-supplied literal text**, same
    already-documented `report/prose.py` deferral (the full
    narrator-perspective/pronoun system, `RUMORS.PAS Set_Person`/
    `Set_Alt`, is a separate unbuilt piece) -- every person/tense
    variant of a side collapses to the same literal name string, e.g.
    `<` and `<2` both become the attacker's name; a true pronoun
    ("he"/"his troops") is never produced.
  - **"Army name" (e.g. "the 231st Bowmen") is never synthesized** --
    there is no ordinal-numbering/naming system anywhere in this
    project (`LNAMES.PAS`/`PRNAMES.PAS` territory, a separate, entirely
    unbuilt subsystem). Every function takes caller-supplied
    display-name strings for armies/provinces/kingdoms, the same
    values-dict pattern `prose.render()` itself already uses --
    `describe_battle()` silently skips a column/army whose id has no
    entry in the caller-supplied name map, rather than inventing one.
  - `parse_template_choices()` also gives this project its first
    from-scratch `.X`/`.X2` file-format parser (header line
    `"<choices> <blockdepth>"`, sourced from `RUMORS.PAS`'s own
    `READLN(sf,choices,blockdepth)`), for future phases that want to
    load real template files directly instead of hand-transcribing them.
    Only `blockdepth == 1` is supported (true of every battle template
    inspected this phase) -- raises `NotImplementedError` rather than
    guessing at multi-line blocks.
  - Non-breaking: full suite passed unchanged (1418 passed) before any
    new tests were written. 21 new tests added (1439 passed total) in
    `test_turn_report.py`, covering the template parser, the margin
    bucketing, each render function's real-template output against
    hand-verified rendering traces, and one full `describe_battle()`
    integration case plus an all-skipped (tie, no army names) edge case.
- **Phase 62**: `turn/aspy_execution.py`, closing the
  report-generation half of ASpy's Phase 26 gap -- "intelligence-report
  content ... needs a report-generation system this project doesn't have
  at all" was true when that was written; Phases 58/61 now give this
  project exactly that. Only the *data* side is built here (matching the
  "data first, prose later" split Phases 58/61 already established for
  battle outcomes); rendering a `SpyReport` into English sentences is a
  natural, still-open follow-up.
  - **`execute_aspy()`** builds rulebook [3.14]'s report -- "owner,
    owners of adjacent provinces, ... army types recruitable there, and
    whether the province is the capital" -- for the caster's own current
    province, reusing `turn/movement.py neighbors()` for adjacency and
    `turn/recruit.py is_army_type_compatible_with_race()` (the same
    table Recruit itself already resolves against) for recruitable
    types. Returns `None` if the caster's own province isn't a known
    `ProvinceState` -- insufficient data, not a guessed report.
  - **"A character may only Spy on a province he is actually in" is read
    literally**: the report always covers `LeaderState.location`, and
    `SpyProvinceRequest.target_province` (the raw, player-typed int) is
    decoded but deliberately never trusted or cross-checked --
    `turn/aspy_defend_decode.py`'s own docstring already flags that no
    Pascal source confirms whether that field shares
    `turn/hex_numbering.py`'s empirically-inferred numbering space or
    the host's separate internal `x*XMULT+y` arithmetic. Trusting the
    rule's own text over an unconfirmed number space matches how Recruit
    and Practice already resolve against the acting leader's own
    location rather than a player-typed target.
  - **Taxation of the province is not reported** -- there is still no
    per-province tax-base model anywhere in this project;
    `ProvinceState.tax_modifier_percent` is a *modifier* (Bless/
    Earthquake, Phase 59), not a base tax figure. `SpyReport` omits the
    field rather than guessing a number.
  - **`ActionCode.ASPY` now dispatches to real execution** in
    `turn/plan_dispatch.py` (`_dispatch_aspy`), replacing the
    decode-only wiring from Phase 26. `ActionCode.DEFEND` stays
    decode-only in `plan_dispatch.py` itself -- its own reactive
    battle-joining was separately wired into `turn/turn_processor.py`
    back in Phase 57.
  - Non-breaking: full suite passed unchanged (1439 passed) before any
    new tests were written -- one pre-existing dispatch test
    (`test_dispatch_aspy_is_decode_only`) asserted the now-superseded
    decode-only behavior and was renamed/rewritten, a comment/behavior
    fix flagged the same way Phase 59/60's "representative unmodeled
    spell" test swaps were, not a silent behavior change. 9 new tests
    added (1448 passed total): 8 in `test_aspy_execution.py` (own
    province/owner, ignoring the raw target field, unowned province,
    adjacent owners, unknown-neighbor omission, recruitable types,
    capital true/false) plus the rewritten dispatch test.
- **Phase 63**: extends `report/turn_report.py` with two more
  real, standalone templates -- `render_uncontested_conquest()`
  (`HostAK/TP/PROSE/CONQ.X`, a Move that conquers an undefended
  province, no battle dispatch involved at all) and
  `render_spy_report_opening()` (`HostAK/TP/PROSE/SPY.X`,
  `SAY.PAS _LSpy`), the report-opening sentence Phase 62 flagged as its
  own natural follow-up.
  - **Research first traced `RUMORS.PAS Set_Intel`** (the procedure
    `turn/aspy_defend_decode.py` already cites as proof `obj` is
    engine-consulted) to see whether it composes the actual "owner /
    adjacent owners / recruitable types / capital" sentences a
    `SpyReport` needs. It doesn't -- `Set_Intel` computes cross-kingdom
    *report-visibility* levels (`intel_lev`, gating what *other* kings
    learn about a spying event in *their own* reports), a separate,
    unbuilt system. ~~No dedicated template for those specific facts
    turned up anywhere in the available Pascal source~~ (`SPDESC.X2`/
    `FPDESC.X2` looked promising by name but are Search Feature-power
    descriptions, unrelated) -- found in Phase 115, sitting in
    `SAY.PAS` immediately after `_LSpy`'s own dispatch in the very same
    procedure. **Rendering the rest of `SpyReport` is mostly closed as
    of Phase 115** -- see its own entry below for the two facts still
    genuinely blocked on an unbuilt capability.
  - **A real discovery while transcribing `CONQ.X`**: 2 of its 4 real
    variants use the `/S` (Sea-terrain) marker `report/prose.py`
    deliberately doesn't resolve (Phase 58's own documented gap).
    `render_uncontested_conquest()` has no `is_sea_province` parameter
    to resolve it with, so `_CONQ_TEMPLATES` keeps only the 2
    `/S`-free variants rather than letting the function crash on a
    coin-flip -- documented in the module docstring and the constant's
    own comment, not silently dropped.
  - **`SPY.X`'s own `^B`/`^E` markers** are Turbo Pascal's
    King-exclusion narrator markers (`RUMORS.PAS Set_Person`/
    `Set_Alt`, already flagged out of scope by `report/prose.py`'s own
    docstring) -- `render_spy_report_opening()` elides both
    (substitutes empty string) rather than guessing what a full
    narrator-perspective system would put there.
  - Non-breaking: full suite passed unchanged (1448 passed) before any
    new tests were written. 5 new tests added (1453 passed total) in
    `test_turn_report.py`, covering both real usable CONQ.X variants
    and three SPY.X variants (including the King-exclusion elision and
    a variant exercising both `/R` and `{}` resolution together).
- **Phase 64**: wires the numeric-superiority outflanking rule
  into `turn/battle_resolution.py resolve_battle` -- the *other*
  rulebook trigger `turn/battle_line.py column_strength`'s
  `outflank_second_line` parameter was originally built for (Phase 6),
  left unwired ever since (only the *non-humanoid rear-targeting*
  trigger got wired, in Phase 39).
  - `RULES.AK` ~line 1362 (quoted in full): "If a battle line is shorter
    than the terrain allows, the flanking second-line units of a force
    which is superior in numbers may outflank the enemy force. If they
    do that, they count as 100% strength instead of 50%." Eligibility is
    computed once per side in `resolve_battle`: this side's own unit
    count must exceed the opposing side's, *and* `line_length` must be
    strictly less than `terrain_line_length_cap` -- a `None` cap (unknown
    terrain) makes this false, not true, matching the same
    insufficient-data-isn't-a-guessed-result convention used throughout
    this project. The rulebook's own worked example (~line 1770: two
    second-line Legions "will not be penalized 50% because they will be
    able to outflank the enemy") confirmed this is unconditional once
    eligible, not a chance roll -- matching `column_strength`'s existing
    non-probabilistic contract, so no new `rng` consumption at all.
  - OR'd together with the already-wired rear-targeting driver (a column
    can be eligible for either reason, or both; the 100% effect itself
    never stacks, since it's a single boolean flag either way).
  - **Not modeled**: `RULES.AK`'s related nemesis-selection sentence a
    few paragraphs later ("If more than one of your units are eligible
    to be a nemesis due to overflight or outflanking, one of them is
    chosen at random") -- a separate mechanic about *which* unit
    receives nemesis targeting when several qualify, not this rule's own
    100%-strength effect. `turn/battle_line.py
    apply_nemesis_penalties`'s own documented column-pairing
    interpretation doesn't yet account for outflanking eligibility
    specifically -- left as its own distinct, still-open gap rather than
    folded into this phase.
  - Non-breaking: full suite passed unchanged (1453 passed) before any
    new tests were written -- every existing test either passes no
    `terrain_line_length_cap` (making the new condition unconditionally
    false) or sets it exactly equal to the already-count-capped
    `line_length` (the "terrain is the binding constraint" case, also
    false), so none of them were perturbed by the new logic. 3 new tests
    added (1456 passed total) in `test_battle_resolution.py`: the
    eligible-and-boosted case, the terrain-is-the-binding-cap case, and
    the no-cap-supplied case.
- **Phase 65**: widens `turn/battle_line.py
  apply_nemesis_penalties`'s eligibility rule -- the user directly asked
  whether the nemesis-selection nuance Phase 64 flagged as unmodeled
  ("if more than one of your units are eligible to be a nemesis due to
  overflight or outflanking, one of them is chosen at random") could be
  built; chose to tackle only its overflight half, since `RULES.AK`
  gives no further text connecting the outflanking half to nemesis
  eligibility specifically.
  - `RULES.AK` (quoted in full, same paragraph as the nemesis penalty
    itself): "A unit is a nemesis to its opponent if it's on the front
    line or it's an air unit flying against a unit behind the front
    line. If more than one of your units are eligible to be a nemesis
    due to overflight or outflanking, one of them is chosen at random."
  - For each of `own_column`'s units, the eligible opposing
    nemesis-inflictors are now: (1) the opposing front-line unit --
    always eligible, against every one of `own_column`'s units
    regardless of depth (unchanged from Phase 33); (2) any *effectively*
    overflight unit (Phase 43's Druidic held-back carve-out still
    applies) anywhere in the opposing column, but *only* against
    `own_column`'s units at depth >= 1 ("flying against a unit **behind**
    the front line" -- never against `own_column`'s own front-line
    unit). When eligibility has more than one member, `rng.choice`
    picks one before the nemesis-type check runs against just that one.
  - **Backward-compatible by construction, not by accident**: `rng` (a
    new parameter, threaded through from `resolve_battle`) is only ever
    actually called when a column has a genuinely ambiguous case (an
    opposing overflight unit stacked *behind* that opposing column's own
    front line) -- true of zero fixtures anywhere in this project's test
    suite before this phase, confirmed by the non-breaking check passing
    unchanged.
  - **"...or outflanking" stays unmodeled**, documented explicitly
    in `apply_nemesis_penalties`'s own docstring: whether it means an
    outflanking-eligible *own* second-line unit becomes an eligible
    inflictor itself (against whom?), or something else, isn't
    resolvable from the available source without guessing -- left as
    its own distinct, still-open gap rather than forcing an unconfident
    reading.
  - Non-breaking: full suite passed unchanged (1456 passed) before any
    new tests were written. 3 new tests added (1459 passed total) in
    `test_battle_line.py`: the widened-eligibility-triggers-the-penalty
    case, the same setup with `rng.choice` landing on the non-overflight
    candidate instead (proving genuine randomness, not "overflight
    always wins"), and the Druidic-blocked-overflight-stays-excluded
    case.
- **Phase 66**: `turn/pursue_execution.py step_toward_target`/
  `advance_pursuit` -- a deliberately narrow first step toward Pursue's
  ([3.16]) still-open persistent multi-phase chase, confirmed with the
  user before implementation. Researching the full picture first
  (quoted in full, `RULES.AK` [3.16]) showed the real rule is much
  bigger than "reroll the catch-up chance each phase": the pursuer
  actually moves province to province toward a moving target, later
  phases' own orders are pre-empted until the chase resolves, and there
  are Patrol ([3.16]'s "Characters On Patrol" self-Pursue variant) and
  Defend-cancellation interactions ("if he receives a Move, Pursue or
  Trail order, the Defend order is cancelled") on top -- a subsystem
  roughly the size of `turn/turn_processor.py` itself, not a single
  phase. The user chose the smallest safe slice over both "skip it" and
  "plan the whole subsystem now".
  - **`step_toward_target`**: one greedy hex step minimizing
    `turn/movement.py hex_distance` to the target -- the mechanical
    piece of "he will keep moving from province to province until he
    arrives", reusing `neighbors()`/`hex_distance()` rather than
    building new pathfinding (same straight-line abstraction
    `execute_pursue`'s own catch-up-chance distance already uses).
  - **`advance_pursuit`**: moves the pursuer and every army they command
    one step closer (same leader-plus-armies convention
    `turn/move_execution.py` already uses), then calls the existing
    `execute_pursue` fresh at the new, shorter distance -- reuses
    Phase 51/53's catch-up roll and army-battle/encounter resolution
    entirely unchanged, adding only the movement step in front of it.
  - **Deliberately not attempted, confirmed with the user as future
    work**: auto-wiring this into `turn/turn_processor.py`'s phase
    loop (would require resolving whether an unresolved Pursue preempts
    the pursuer's own later-phase orders, and how that interacts with
    Multiple Contingents/mutual-encounter detection); movement-point
    cost for the step; Patrol; Defend-cancellation; and Pursue's own
    catch-conditional later actions. `advance_pursuit` is a standalone,
    explicitly-invoked primitive today, not automatic turn behavior.
  - Non-breaking: full suite passed unchanged (1459 passed) before any
    new tests were written. 4 new tests added (1463 passed total) in
    `test_pursue_execution.py`.
- **Phase 67**: `turn/turn_processor.py
  _apply_defend_cancellations` -- Defend's own cancellation rule,
  directly relevant now that Phase 66's Pursue research surfaced its
  exact wording. `RULES.AK` [3.15] (quoted in full): "A general with
  Defend orders may use the rest of his actions to practice, explore,
  etc. If he receives a Move, Pursue or Trail order, the Defend order is
  cancelled."
  - Removes a leader from `active_defends` the moment their own plan
    reaches an LMOVE/PURSUE/TRAIL phase, running *before*
    `_apply_defend_reinforcements`'s own check each phase -- a general
    who's moving/pursuing/trailing this phase is no longer standing by
    to react to an invasion this same phase either. Cancellation keys
    only off the order *type* the leader's own plan contains at that
    phase, not whether the underlying move/pursue/trail itself actually
    succeeds -- "if he **receives**" an order is read as the order being
    given, not the order landing.
  - **Only this cancellation trigger is modeled.** The rulebook's other
    one -- "a character's Defend order is cancelled if he loses a
    battle, to prevent further needless defeats" -- stays a distinct,
    still-open gap: it needs this leader's own battle outcome *this same
    phase*, not yet available at the point `_apply_defend_cancellations`
    runs (battles dispatch later in the phase, across several different
    code paths -- solo, Multiple Contingents, contested-province
    rebattles, and Pursue's own army-vs-army catch-up each produce their
    own result shape) -- left unattempted rather than guessed at.
  - Non-breaking: full suite passed unchanged (1463 passed) before any
    new tests were written. 4 new tests added (1467 passed total) in
    `test_turn_processor.py`: LMOVE/PURSUE/TRAIL each cancel an active
    Defend before its next reinforcement check, and an unrelated action
    (WAIT) doesn't.
- **Phase 68**: `turn/trail_execution.py advance_trail` --
  the same scoped multi-phase chase step Phase 66 added for Pursue,
  now for Trail. [3.17] draws the parallel explicitly: "Like the
  Pursue order, the Trail order ends when the character finds and has
  spied on the character for one phase."
  - Mirrors `advance_pursuit` exactly, reusing `turn/
    pursue_execution.py`'s own `step_toward_target` primitive rather
    than duplicating hex-stepping logic: one greedy hex step toward the
    target's current location, then a fresh `execute_trail` catch-up
    attempt at the new, shorter distance. Simpler than Pursue's own
    version in exactly one respect -- a Trail order never has armies to
    move alongside the leader, since `execute_trail` already enforces
    "a character leading an army may not be ordered to Trail".
  - Same scope boundary as Phase 66, carried over unchanged: not
    auto-wired into `turn/turn_processor.py`'s phase loop, no
    movement-point cost -- a standalone, explicitly-invoked primitive.
  - Non-breaking: full suite passed unchanged (1467 passed) before any
    new tests were written. 2 new tests added (1469 passed total) in
    `test_trail_execution.py`.
- **Phase 69**: `ProvinceState.explored_percent_by_kingdom` --
  finally unblocks the exploration-advantage strength bonus flagged
  since Phase 9 and explicitly documented as blocked in Phase 35.
  `RULES.AK`'s [6.3] "ARMY STRENGTH NOTES" (quoted in full): "The side
  with the better exploration of the contested province will also have
  up to a 25% advantage, if they have explored 100% of the province and
  the other side has not explored it." `turn/strength.py
  exploration_advantage_multiplier` has implemented the formula itself
  since Phase 9 -- the only missing piece was ever real per-kingdom
  data to feed it, since the pre-existing `explored_percent` field is a
  single shared scalar with no way to ask "how much has *this* kingdom
  explored it."
  - **Purely additive**: every write site that already updates
    `explored_percent` (`turn/move_execution.py execute_move`, `turn/
    plan_dispatch.py`'s EXPLORE branch, `turn/turn_processor.py`'s
    multi-attacker LMOVE branch) now *also* calls the new `turn/
    move_execution.py record_kingdom_exploration()`, which seeds from
    that acting kingdom's own prior per-kingdom entry (0 if never
    recorded) rather than the shared scalar. In the multi-attacker
    branch this is a real behavior improvement over the pre-existing
    shared scalar, not just a parallel write: previously only the
    *last* mover in the loop's own contribution survived (a documented
    pre-existing quirk), while now every uniting kingdom gets its own
    independently tracked percentage.
  - **`turn/battle_orchestrator.py fight_battle`** reads both sides'
    entries once per battle -- the attacker's own `attacker_kingdom_id`,
    and the defending province's own `owner_kingdom_id` for the
    defending side (an allied co-defender who isn't the owner isn't
    separately tracked, a documented simplification) -- and threads
    them through `_build_battle_units`'s new `own_explored_percent`/
    `enemy_explored_percent` parameters into every unit's `turn/
    strength.py compute_effective_strength` call.
  - **A kingdom that owns a province is not automatically seeded at
    100%.** There is no data anywhere in this project for "how long has
    this kingdom held it" or "did they explore it before this
    simulation's own tracked history began," and guessing either would
    contradict this project's own no-guessing convention -- a longtime
    owner who never issued an explicit Explore/Move-into order into
    their own province in a recorded turn reads as 0% here, same as
    anyone else with no history. Missing entries for *both* sides
    default to 0, which `exploration_advantage_multiplier(0, 0)` reads
    as no advantage either way -- a neutral, not a guessed, default.
  - Non-breaking: full suite passed unchanged (1469 passed) before any
    new tests were written -- the new field defaults to an empty dict
    and every new parameter defaults to 0, so no existing caller's
    behavior changed. 6 new tests added (1475 passed total) across
    `test_move_execution.py`, `test_plan_dispatch.py`,
    `test_battle_orchestrator.py`, and `test_turn_processor.py`.
- **Phase 70**: `turn/turn_processor.py
  _continue_active_pursuits`/`_register_pursuit_continuation` -- wires
  Pursue/Trail's own persistent multi-phase chase into the phase loop,
  resuming the work Phase 66/68 deliberately left unattempted. `RULES.AK`
  [3.16] (quoted in full in earlier phases' notes): "A character can be
  ordered to chase after another character for the rest of the turn...
  You can specify other actions on phases 2 through 5 which will be
  attempted if the pursuit is resolved before the end of the gameturn."
  Confirmed with the user before implementation as a scoped step, not
  the whole originally-floated ask (which also named Patrol and Defend's
  battle-loss cancellation -- both stay open, see below).
  - **Preemption**: a new `active_pursuits: dict[int, _ActivePursuit]`
    local to `run_turn()` tracks every leader with a still-unresolved
    Pursue/Trail. At the start of each phase, any leader listed there
    has their real plan entry for *that* phase dropped entirely from
    `entries` -- before Multiple Contingents/Practice/mutual-encounter
    detection ever sees it -- and a `_continue_active_pursuits` call
    dispatches one `advance_pursuit`/`advance_trail` step for them
    instead, at `segment_index=-1` (the same not-tied-to-a-real-segment
    sentinel `_dispatch_contested_rebattles` already uses).
  - **Resolution is checked once, at the phase's own start**: if a
    chase resolves *during* a phase's own continuation dispatch, that
    phase's original order is still lost (already dropped before the
    outcome was known) -- only the *following* phase's order dispatches
    normally. The rulebook doesn't disambiguate same-phase ordering
    here; this follows the same "act on what's known at the start of
    the phase" principle Defend cancellation/reinforcement (Phase 57/67)
    already use, rather than guessing at a same-phase reordering rule
    this project has no precedent for.
  - **Registration**: a freshly-dispatched PURSUE/TRAIL phase (via the
    ordinary `_dispatch_single` path) that comes back with the specific
    "did not catch up this phase"/"did not find the target this phase"
    reason -- and only that reason, not a refused encounter or a
    terminal not-found/army-mismatch failure -- is registered into
    `active_pursuits` for continuation next phase onward.
  - **Explicitly still out of scope, confirmed with the user as a
    scoped step rather than the whole floated ask**: "Characters On
    Patrol" (self-targeting Pursue, [3.16]) is never registered for
    persistence -- its detect-any-adjacent-enemy semantics are
    structurally different from directed chase-toward-one-target and
    need a different implementation. Defend's other cancellation
    trigger ("cancelled if he loses a battle") remains the same open
    gap `_apply_defend_cancellations` already documented in Phase 67. A
    Pursue/Trail resolved via the mutual-encounter dispatch path is
    never registered for persistence either -- only the plain
    single-leader path is. Continuation steps carry no movement-point
    cost and never trigger Defend reinforcement, matching
    `advance_pursuit`/`advance_trail`'s own already-documented scope.
  - Non-breaking: full suite passed unchanged (1475 passed) before any
    new tests were written -- the preemption/continuation logic only
    ever runs for a leader already inside `active_pursuits`, which
    starts empty and nothing in the existing test suite issues a
    Pursue/Trail that stays unresolved across a phase boundary. 3 new
    tests added (1478 passed total) in `test_turn_processor.py`: an
    unresolved Pursue preempts a later LMOVE order and continues the
    chase via one hex step until it resolves, then the leader's next
    real order dispatches normally again; the same for Trail; and a
    Pursue with no such target (a terminal reason, not "did not catch
    up") is confirmed to *not* preempt anything.
- **Phase 71**: `turn/patrol_execution.py` (new) +
  `turn/turn_processor.py _apply_patrol_cancellations`/
  `_dispatch_active_patrols` -- "Characters On Patrol" ([3.16]), the
  self-targeting-Pursue standing order Phase 70 explicitly deferred.
  Confirmed with the user (options: Patrol, Defend's battle-loss
  cancellation, or Feature model foundations) as the next scoped step.
  `RULES.AK` [3.16] "Characters On Patrol", quoted in full in `turn/
  patrol_execution.py`'s own module docstring (rules a-i): "This is
  like the Defend order, except whenever the character hears of an
  intruding character, he chases him down... Write this order by
  having the character 'Pursue' his own character number."
  - **`find_patrol_target`/`execute_patrol`**: rules (a) armyless-only
    (both patroller and candidate), (b) current-plus-adjacent-hex
    coverage, (c) enemy-only (reading "enemy" the same way `turn/
    turn_processor.py _sees_nonallied_defender` already does --
    kingdomless is never automatically hostile), (f) owned/allied
    territory, (g) skill-gated ("best skill in Archery, Melee or
    Magic," with "Magic" read as the max of this project's five magic
    schools -- no single "Magic" `Ability` exists), (h) most-threatening
    tiebreak (rule (h)'s own "point (7)" cross-reference doesn't exist
    anywhere in the available `RULES.AK` text -- an orphaned reference
    in the source rulebook itself, falls back to rule (g)'s own metric
    plus lower `leader_id`), and (i) the Spy Table's 50%-wander roll
    for an adjacent-hex (not same-hex) interception at Spy skill 0,
    guaranteed at skill 1+ (the rule states only the skill-0 case).
    Combat resolution once a target is confirmed reuses the exact same
    armyless-Encounter core `execute_pursue` already uses.
  - **Explicitly not modeled, a genuine data-model gap**: rule (e)
    ("unable to detect... if he is using his Spy or Thief ability that
    gameturn") needs per-turn ability-usage tracking this project's
    `GameState` has nowhere -- the same category of gap already
    declared for ASpy's "Chance of Escaping Notice" column.
  - **Standing-order persistence lives in `turn_processor.py`, not the
    new module**: a new `active_patrols: dict[int, PursueRequest]`
    local to `run_turn()` -- a self-targeting PURSUE phase is detected
    and dropped from `entries` before anything else sees it (declaring
    Patrol, never dispatching as an ordinary nonsensical self-Pursue),
    and `_dispatch_active_patrols` re-checks every phase for every
    active patroller. Rule (d) ("stays active until the next Move,
    Trail or Pursue order; other orders... are used if there is no
    current threat"): `_apply_patrol_cancellations` reuses
    `_apply_defend_cancellations`'s identical LMOVE/PURSUE/TRAIL
    trigger set verbatim (same rulebook wording for both), and a
    leader's own real order for a phase is only preempted when a
    threat is actually found that phase -- unlike Phase 70's directed
    chase (which always re-attempts every phase while unresolved),
    Patrol never "resolves" and stops on its own; only cancellation or
    an absent threat lets the next order through.
  - Non-breaking: full suite passed unchanged (1478 passed) before any
    new tests were written -- the one pre-existing test that dispatched
    a self-targeting Pursue through the old (already-documented-as-
    nonsensical) path needed its assertion updated to the new, correct
    "Patrol declaration, no other leader around, nothing to report"
    outcome, not a regression. 26 new tests added (1504 passed total):
    23 in `test_patrol_execution.py` covering `find_patrol_target`'s
    every rule and `execute_patrol`'s Spy Table roll and combat
    resolution, and 3 in `test_turn_processor.py` covering the standing
    order's interception-preempts-a-scheduled-order behavior, the
    no-threat-lets-it-through behavior, and cancellation by a later
    Move order (even with an intruder still adjacent, proving
    cancellation wins over interception for that same phase).
- **Phase 72**: `turn/turn_processor.py
  _apply_defend_battle_loss`/`_extract_battle_winner` -- Defend's other
  cancellation trigger, the last of the three options (Patrol, this,
  Feature model foundations) floated back when Phase 70 first named
  the gap. `RULES.AK` [3.15] (quoted in full in earlier phases' notes):
  "A character's Defend order is cancelled if he loses a battle, to
  prevent further needless defeats."
  - **Scoped to the one battle a Defend leader can ever actually enter
    in this project's simulation, confirmed by re-reading
    `_apply_defend_cancellations`'s own reasoning**: a Defend leader
    never moves or fights except via `_apply_defend_reinforcements`'s
    own relocation (any LMOVE/PURSUE/TRAIL order of their own would
    already cancel Defend via the *other* trigger, Phase 67, before
    they could ever enter a battle that way) -- so checking only the
    reinforcement-triggered battle is the complete scenario space for
    this codebase, not a narrow slice of a bigger one.
  - **`_apply_defend_reinforcements` now returns `{defender_leader_id:
    target}`** for every reinforcement it performs, instead of
    `None` -- `run_turn()` uses it to build `reinforced_by_target` and
    look up that exact battle's `BattleResult.winner` once this same
    phase's LMOVE dispatch (solo or Multiple Contingents -- both call
    sites are wired) resolves it. `_extract_battle_winner` reads
    whichever of `MoveExecutionResult.battle_report`/
    `MultiAttackerMoveResult.battle.report` the dispatch produced.
  - **A new `defeated_while_defending: set[int]`, persistent across
    phases within one `run_turn()` call, unlike `active_defends`
    itself**: once a leader's reinforcement battle comes back
    `winner == "attacker"`, they're added here and permanently blocked
    from ever registering into `active_defends` again this call, even
    if their own plan re-issues a fresh DEFEND order at a later phase
    -- necessary because `active_defends` already unconditionally
    drops a leader after one reinforcement (Phase 57's own "consumed
    after first reinforcement" rule) regardless of outcome, so without
    a separate persistent flag this trigger would have no observable
    effect on the common case (only the rare "re-declares Defend after
    already losing" case actually needs it, and that's exactly the
    case tested).
  - **Testing note**: an early version of the test compared a *second*,
    unrelated invasion's own contested/uncontested status, which turned
    out to be confounded by the losing garrison's own natural retreat
    (`turn/retreat.py`) landing in the same coverage-area hex being
    tested -- coverage and retreat both key off "neighbors of the
    leader's post-battle location," so they can collide. Fixed by
    asserting on the defender leader's own final location instead
    (only `_apply_defend_reinforcements`'s own relocation code ever
    moves it, so it's retreat-independent).
  - Non-breaking: full suite passed unchanged (1504 passed) before any
    new tests were written -- `_apply_defend_reinforcements`'s new
    return value is purely additive, and `defeated_while_defending`
    starts empty and nothing in the existing suite re-declares DEFEND
    after a reinforcement battle. 2 new tests added (1506 passed
    total) in `test_turn_processor.py`: a losing reinforcement battle
    blocks a later DEFEND re-declaration from ever relocating the
    leader again, and a winning one doesn't.
- **Phase 73**: `turn/battle_orchestrator.py
  fight_multi_attacker_battle` -- fixes a real, previously-untested
  crash: when Multiple Contingents ([7.8]) splits several attackers
  into *separate* (non-united) groups against the same province
  (`multiple_contingents.py group_attackers_into_battles`'s own
  unsourced unite-chance roll), each group's `fight_battle()` call
  runs sequentially against whatever's left of the province's
  defenders. If an earlier group cleanly sweeps them, a later group's
  own `fight_battle()` call previously raised `ValueError("no
  defending armies at this province to fight")` -- uncaught anywhere
  in the dispatch chain, so it crashed the *entire* `run_turn()`, not
  just the colliding leaders' own results. Confirmed reachable from
  real multi-leader play (not just hypothetical): two unallied
  kingdoms' leaders moving from different origins against a weakly
  defended province, whenever the different-origin 30% unite roll
  fails.
  - **Fix**: before calling `fight_battle()` for each group, checks
    for any remaining non-allied defender at the province (the same
    filter `fight_battle()` itself already uses internally). If none
    are left, synthesizes an uncontested `BattleReport(battle_result=
    BattleResult(winner="attacker"), conquered=True)` instead of
    calling `fight_battle()` again -- the same "no defenders present ->
    uncontested" reading `turn/move_execution.py execute_move()`
    already gives a lone attacker walking into an empty enemy-owned
    province. `RULES.AK` [7.8] doesn't say how several simultaneous,
    unrelated invasions of the same province are meant to interact
    once one has already resolved -- a documented, unsourced-but-
    reasonable design choice, the same category as this function's own
    `SAME_ORIGIN_UNITE_CHANCE`/`DIFFERENT_ORIGIN_UNITE_CHANCE`
    constants. Since the *first* group's own `fight_battle()` call
    already transfers province ownership on a clean sweep, the
    synthetic report doesn't need to repeat that -- it only needs to
    let the caller's existing post-battle bookkeeping (movement cost,
    army/leader relocation) proceed correctly for the second group's
    own leaders too.
  - Non-breaking: full suite passed unchanged (1506 passed) before any
    new tests were written. 1 new test added (1507 passed total) in
    `test_battle_orchestrator.py`: two separate groups attacking the
    same weakly-defended province, the first cleanly sweeps, the
    second's own dispatch no longer raises and instead reports an
    uncontested conquest.
- **Phase 74 (current)**: `report/prose.py` -- resolves the "/S"
  (Sea-terrain) prose marker, one of the three choice markers Phase 58
  deliberately left as an honest `NotImplementedError` rather than a
  guessed 50/50 random choice. `PROSE.TXT` (quoted in full): "The '/S'
  symbol divides between two possible choices. The left choice is used
  in a land situation, the right choice is for a sea or underwater
  situation." Unlike `/R`, this was never random at the Pascal level
  (confirmed from `Say_Options`'s own `Left_Choice` function, already
  cited in Phase 58's own note) -- a live crash risk, not just a gap:
  several of `report/turn_report.py`'s own already-transcribed real
  battle templates (`_MARGIN_TEMPLATES`, `_WINNER_TEMPLATES`,
  `_DEFWIN_TEMPLATES`, `_RETREAT_TEMPLATES`) carry "/S" markers that
  raised `NotImplementedError` the moment `pick_variant` happened to
  select one of them.
  - **`render()`'s new `is_sea: bool = False` keyword-only parameter**
    drives it -- default `False` (the land choice) means every
    pre-Phase-74 caller's behavior is unchanged. `/R` and `/S` now
    share one merged choice-resolution loop (`_resolve_choice_markers`,
    renamed from `_resolve_random_choices`): identical word-boundary
    split logic, only the left-vs-right decision rule differs (a coin
    flip for `/R`, `is_sea` directly for `/S` -- so `/S` never consumes
    a random value at all, confirmed by a dedicated test with an empty
    `ScriptedRandom`).
  - **`report/turn_report.py`**: `is_sea` threaded through every
    function whose own template set carries a "/S" marker --
    `render_column_clash`, `render_battle_winner`, `render_retreat`,
    `render_uncontested_conquest`, and `describe_battle` (which passes
    its own `is_sea` down to all of the above uniformly, since every
    sentence in one battle narrative describes the same province).
    `_CONQ_TEMPLATES` is restored to all 4 of CONQ.X's real variants
    (transcribed verbatim from the raw file bytes -- plain ASCII text
    there, unlike RETREAT.X/WINNER.X's compiled control-byte encoding
    Phase 61's own note describes) -- the 2 left out since Phase 63
    specifically because `/S` wasn't resolvable yet.
  - Non-breaking: full suite passed unchanged (1507 passed) before any
    new tests were written -- the one pre-existing test that used `/S`
    as its "still-unsupported marker" example needed to switch to `/F`
    (still deferred), since `/S` is exactly the gap this phase closes,
    not a regression; and `render_uncontested_conquest`'s own existing
    "second variant" test needed its `choice_indices` updated from `1`
    to `3`, since inserting the 2 restored variants at indices 1-2
    shifted it down -- both expected, not accidental breakage. 15 new
    tests added (1522 passed total) across `test_prose.py` and
    `test_turn_report.py`.
- **Phase 75 (current)**: Feature/Monster model foundations (rulebook
  [3.2] Explore, [3.3] Search Feature), the type-and-instance shape a
  future Search-resolution/world-generation phase will need, chosen by
  the user from a post-Phase-74 "what's next" menu.
  - **`models/monster.py`** (new): the `monster` enum, transcribed
    verbatim from `CTBOTH.PAS` (61 declared values -- 60 real species
    plus the real `Nomonster` sentinel; `nmonsters = 60` apparently
    counts only the species). `MONSTER_HP_BANDS` transcribes [3.2]'s
    "Weak/-/Large-Strong/Powerful/Very Powerful" hit-point descriptor
    table verbatim, including the rulebook's own unlabeled second row.
    `MonsterSpeed` (Fast/Medium/Slow) is confirmed by [5.6] Flee's
    20%/50%/80% flee-chance tiers. `MONSTER_STATS` transcribes 6 of the
    7 rows of `RULES.AK`'s own "Monster Table" (itself labelled
    "[5.9]" in the source -- a duplicate section number versus the
    table of contents' distinct [5.9] "Victory and Death", a rulebook-
    file quirk, not a transcription error here) -- **the 7th row,
    "Demon", is deliberately excluded**: the Pascal enum has no plain
    `Demon` member, only `BalDemon`/`MarDemon`, and nothing disambiguates
    which (or both) the table row describes.
  - **`models/feature.py`** (new): `FeatureType` (32 values, transcribed
    from `CTBOTH.PAS`'s `feature` enum) and `Feature`, a per-instance
    dataclass (`feature_id`, `coord`, `kind`, `guardian_monster`,
    `looted`, `discovered_by_kingdom: dict[int, int]` -- a per-kingdom
    discovery level, 0 undiscovered .. 3 fully known, mirroring
    `ProvinceState.explored_percent_by_kingdom`'s own Phase 69 shape).
    Confirmed directly from `REPORTS.PAS`'s feature-report-printing code
    that a feature is its **own map entity with its own coordinate**,
    not a property of `ProvinceState` -- a province only carries a
    presence bitflag, and the report loop explicitly handles more than
    one feature sharing a coordinate, matching [3.2]'s "can sometimes be
    more than 1 feature in a province." **Replaces (not extends)**
    `models/map.py`'s old, never-populated `Feature` stub from Phase 1
    -- removed outright rather than left as unused dead code (this
    project's usual "leave old stubs alone" convention for superseded-
    by-unrelated-work models), since this phase is the direct, intended
    completion of that exact stub, and two same-named `Feature` classes
    would be confusing.
  - **Also resolves a previously-flagged mystery**: the `/F` prose
    marker, flagged unsourced since Phase 58, is confirmed by
    `REPORTS.PAS` (~line 2071-2077) to be a per-feature-instance parity
    trick (`fn and 1`) picking one half of a magic-power-hint string --
    understood now, but **not implemented this phase** (would need
    `prose.py render()` to accept a caller-supplied parity input, a
    small, separate follow-up).
  - `models/game_state.py GameState` gains a `features: dict[int,
    Feature]` registry plus `add_feature()`/`features_at(coord)`,
    mirroring the existing `armies`/`add_army`/`armies_at` pattern
    exactly.
  - **Deliberately out of scope, confirmed structural gaps**: world
    generation (which provinces get a feature, of what kind, guarded by
    what -- no surviving Pascal source, the same "missing main
    turn-processor" gap already flagged for hex adjacency and magic-item
    instance creation), rumor generation ([3.2]'s "about half... false"
    mechanic -- the prose templates exist, the selection logic doesn't),
    Search resolution (needs the still-unbuilt personal Encounter-combat
    resolver `turn/encounter.py`'s own docstring already scopes out),
    and promoting the already-documented 113-member `treasure` enum
    (`turn/use_mi_decode.py`'s own docstring) into a real model.
  - Non-breaking: full suite passed unchanged (1522 passed) before any
    new tests were written -- the one pre-existing test that used
    `models/map.py`'s old `Feature` stub (`tests/test_models.py`) was
    updated to import from `models/feature.py` and use the new
    `Feature(feature_id=..., coord=..., kind=...)` shape, not left
    broken. 15 new tests added (1537 passed total) across two new files,
    `tests/test_monster.py` and `tests/test_feature.py`, plus two new
    `GameState.features` registry tests in `tests/test_game_state.py`.
- **Phase 76 (current)**: `report/prose.py` -- resolves the `/F`
  (feature-parity) prose marker, the mystery Phase 58 first flagged and
  Phase 75 traced to `REPORTS.PAS`'s one-off `fn and 1` split. This
  phase confirms it a second, more direct way and implements it for
  real: `RUMORS.PAS Say_Options`'s own `Left_Choice` function is the
  single shared decision point for *every* `/X` choice marker (`'R'`,
  `'S'`, `'F'`, `'P'`, all one `CASE`), and its `'F'` arm reads
  ``boolean(_feat1 and 1)`` -- the left choice is picked exactly when
  the current feature instance's own id is odd. `render()` gains a
  `feature_id: int | None = None` keyword-only parameter, mirroring
  `is_sea`'s shape from Phase 74, except **with no safe default**: a
  template needing `/F` with no `feature_id` supplied raises
  `ValueError` (unlike `is_sea`'s land-side default, there's no
  non-arbitrary parity to assume for "no feature in context"). `/F`
  never consumes a random value, confirmed by a dedicated test with an
  empty `ScriptedRandom`, same pattern as `/S`.
  - **Unlike `/S`, no real template in the available archive contains
    a literal `/F`** -- checked all 163 files under `HostAK/TP/PROSE/`,
    including every feature-adjacent one (`FPDESC.X2`, `FSPEC.X2`,
    `FSEARCH.X`, `FRUMOR.X`, `MAGFEAT.X2`, `MONSTERS.X2`,
    `ENCSPEC.X2`). This phase implements `/F` purely because it's a
    confirmed, sourced part of the shared `Say_Options` marker engine
    documented in `PROSE.TXT`, not because a real consumer needs it
    yet -- `report/turn_report.py` isn't touched this phase (nothing
    there to wire it into).
  - Non-breaking: full suite passed unchanged (1537 passed) before any
    new tests were written -- the one pre-existing test that used `/F`
    as its "still-unsupported marker" example needed to switch to `/P`
    (still deferred, reads whether the current sentence is a merged
    plural list -- `mlist`, a context this project doesn't have a
    per-render-call source for), since `/F` is exactly the gap this
    phase closes, not a regression. 4 new tests added (1541 passed
    total) in `tests/test_prose.py`.
- **Phase 77 (current)**: `models/treasure.py` -- the `treasure` type
  catalog (113 ordinals, `CTBOTH.PAS` lines 606-637), the transcription
  `turn/use_mi_decode.py`'s own docstring had already flagged as "a
  separate, sizable follow-up" since Phase 24. Unlike `Monster`/
  `FeatureType` (Phase 75), almost every Pascal identifier in this enum
  is deliberately obfuscated nonsense (`hla`, `wcp`, `xle`, ...), so
  `Treasure`'s own member names are systematic category+position names
  instead, with the real human-readable text kept in two separate
  lookup dicts (mirroring `MONSTER_NAMES`).
  - **`TreasureCategory`** (12 groups) and **`TREASURE_CATEGORY`**
    (a full 113-entry mapping) are read directly off the Pascal
    declaration's own blank-line grouping and its two inline comments
    (`{trcharges records origin:}` before the 22 quest items;
    `{Arcane's Valor}` after the 6 named uniques): 15 `ABILITY_ITEM` +
    20 `SPELL_WAND` + 5 `COMBAT_WEAPON` + 4 `LEADERSHIP_WEAPON` + 5
    `ANTI_MAGIC_AMULET` + 3 `MONSTER_COMMAND_ITEM` + 15 `SKILL_BOOK` +
    3 `GOLD_HOARD` + 22 `QUEST_ITEM` + 1 `SENTINEL` + 6 `NAMED_UNIQUE`
    + 14 `UNUSED_EXTENSION` = 113. `USE_MI_TARGET_CATEGORIES` marks the
    only two categories rulebook [5.9] actually invokes via Use_MI
    (wands + books) -- confirming `turn/use_mi_decode.py`'s own
    "35 of 113" count exactly.
  - **Three confirmed 1:1 positional mappings onto existing enums**,
    derived mechanically (not hand-copied) so they can't drift:
    `TREASURE_ABILITY_ITEM`/`TREASURE_BOOK_ABILITY` (`Ability`, 15
    each) and `TREASURE_WAND_SPELL` (`Spell`'s first 20 ordinals) --
    each confirmed two independent ways (`TREASAB.X2`'s own short
    labels, e.g. `"+1 Tactical"`.."+1 Sage"`/`'Cast "Resurrection"...'`
    through `'Cast "Invisibility "...'`, and `TREASURE.X2`'s prose,
    e.g. "The Standard of Command raises your Tactical ability...").
  - **`TREASURE_LABEL`**: `HostAK/TP/PROSE/TREASAB.X2`'s 93 non-empty
    lines, verbatim, covering ordinals 0-92 exactly (the file ends at
    92's "no treasure" -- ordinals 93-112, the 6 named uniques and 14
    unused slots, have no line at all).
  - **`TREASURE_NAME`**: a real proper name extracted from
    `HostAK/TP/PROSE/TREASURE.X2`'s own longer prose, for a *different*
    93 ordinals (0-49, 53-93, 97-98). Cross-checking the file's own
    paragraph content against each expected category **found two real
    gaps in the source itself, not extraction bugs**: the paragraph
    right after ordinal 49's "Crown of Dragon Command" jumps straight
    to "Manual of Speedy Marches" (Force March, ordinal 53) -- skipping
    the Eagle-aid and Whale-aid items and `BOOK_TACTICAL` entirely (3
    missing); and the paragraph right after ordinal 93's "Crown of
    Rohan" jumps straight to "Fang of the Vampire Lord" (ordinal 97) --
    skipping `Amulet_Power`/`Scepter_Life`/`Map_Marauders`, 3 of the 6
    named uniques. Past ordinal 98 the file pads out with generic "it
    is not a magic item" filler (consistent with its own header line,
    `"199 3"`, allocating more template slots than the 113-member enum
    actually uses) -- none of that filler is transcribed. The source's
    own literal typos (`"Seamansip"`, `"GOds Quest"`) are kept verbatim.
  - **Deliberately not attempted this phase**: resolving a real item
    *instance* to its `Treasure` type -- confirmed a *deeper* gap than
    `Feature`'s own "no world generation" problem (Phase 75), since
    there's no general item-instance-creation Pascal source at all,
    only the one narrow Valhalla-visitor `Add_Tr` call site
    `turn/use_mi_decode.py`'s own docstring already named; full
    `TREASURE.X2` flavor-text transcription beyond a short name; and
    wiring `USE_MI_TARGET_CATEGORIES` into an actual Use_MI execution
    resolver (a lookup table alone doesn't unblock execution while
    `UseMIRequest.item_instance_id` still can't be resolved to a
    `Treasure` at all). `models/item.py MagicItem`'s own stub is left
    untouched -- it models a physical item *instance*, a different,
    still-harder concept this phase doesn't complete, unlike Phase 75's
    `Feature` stub replacement.
  - Non-breaking: full suite passed unchanged (1541 passed) before any
    new tests were written -- a brand new file with no existing
    call sites. 12 new tests added (1553 passed total) in
    `tests/test_treasure.py`, covering the full 113-count, every
    category group's exact size, the three positional mappings, and
    both `TREASURE_LABEL`/`TREASURE_NAME`'s documented coverage gaps.
- **Phase 78 (current)**: `turn/movement.py
  step_toward_non_adjacent_target()` -- the chase-toward-a-non-adjacent-
  target pathfinding primitive rulebook [3.1] describes and
  `resolve_move()` has raised `NonAdjacentMoveError` for since Phase 2,
  deliberately following the same split
  `turn/pursue_execution.py step_toward_target`/`advance_pursuit`
  (Phase 66) already used for Pursue/Trail: build and test the pure
  chase-step primitive alone first, wire multi-phase persistence into
  `turn_processor.py` in a later, separate phase (as Phase 70 did for
  Pursue/Trail, four phases after Phase 66).
  - **Rulebook [3.1], quoted in full for the relevant part**: "If a
    character is ordered to move to a hex number, but is not adjacent
    to it, he will move towards it (through friendly hexes, if
    possible.)... The character will stop chasing the province if he
    can't find a legal way to move closer to it in one phase. If there
    are two possible provinces that are both closer to the target
    province, the following priorities are used: 1) Owned or
    Allied-player hex; 2) Enemy-player hex; 3) Hero-owned hex; 4)
    Neutral-player hex."
  - **`HexOwnershipTier`** transcribes that 4-tier priority list
    exactly, as an ordinal-ordered `IntEnum` a caller-supplied `tier_of`
    callback classifies each candidate hex into --
    `step_toward_non_adjacent_target()` itself stays independent of
    `GameState`/`ProvinceState`, matching this project's usual
    primitive/wiring split. **Documented limitation**: this project's
    `ProvinceState.owner_kingdom_id` (`int | None`) has no way to mark
    an unowned province as specifically Hero-ruled versus genuinely
    wild, so a real caller can't currently produce `HERO_OWNED` as
    distinct from `NEUTRAL` -- not fixed here, flagged for whichever
    future phase actually wires a `tier_of` against real `GameState`
    data.
  - **Algorithm**: among ``current``'s neighbors strictly closer
    (`hex_distance`, the same straight-line abstraction
    `step_toward_target` already uses -- no terrain-aware pathfinding)
    to `target` than `current` itself, picks the lowest-tier one
    (ties within a tier broken by Python's own stable `min()`, not a
    further sourced rule -- the rulebook doesn't say). Returns `None`
    -- "stop chasing" -- when no neighbor is closer, quoting the
    rulebook's own sentence verbatim in the docstring. Returns
    `current` unchanged if already at `target`.
  - ~~**Deliberately not wired into `resolve_move()`/`execute_move()`/
    `plan_dispatch.py` this phase**: unlike Pursue/Trail's own
    catch-up (which always resolves against the *target*'s own data),
    a Move chase step lands on an *intermediate* hex whose
    terrain/exploration data is different from the ultimate target's --
    `resolve_move()`'s current signature only takes one caller-supplied
    hex's terrain/explored-percent, describing whichever hex will
    actually be entered. Wiring the chase in for real needs
    `execute_move()` to look up the *intermediate* hex's own province
    data (not the target's) once the geometry decision is known~~ --
    **`execute_move()` wired this in as of Phase 85** -- see that
    phase's own note below. The rulebook's own multi-phase persistence
    rule ("The movement order will override orders in a subsequent
    phase only if the character is practicing in that phase") is still
    a separate, still-deferred follow-up, matching Phase 66's own
    precedent for Pursue/Trail.
  - Also fixes a stale README bullet found while researching this
    phase: the "Not yet implemented" section's own note about
    contested-province forced rebattle was never struck through when
    Phase 55 actually closed it -- corrected above, in Phase 55's
    original section, not left to mislead a future reader.
  - Non-breaking: full suite passed unchanged (1553 passed) before any
    new tests were written -- a new, standalone function with no
    existing call sites. 5 new tests added (1558 passed total) in
    `tests/test_movement.py`, covering the single-closer-candidate
    case, the ownership-tier tie-break (hand-verified against the hex
    grid's own cube-coordinate math), the "stop chasing" `None` case,
    and the already-arrived case.
- **Phase 79 (current)**: `models/feature.py MONSTER_GUARDED_FEATURE_TYPES`
  -- a real, sourced piece of the world-generation puzzle, found while
  researching what else `CTBOTH.PAS` might still have to offer:
  `monfeat`/`mfeat1`/`mfeat2` (~line 803-833, `type monfeat =
  array[monster] of feature`), giving every real `Monster` species a
  `(primary, secondary)` preferred `FeatureType` pair to guard.
  - **Confirmed genuinely world-generation-side, not player-turn-
    processing data**: the whole table sits inside a `{$IFDEF
    Moderator}` compile block -- only ever built into the Moderator
    (game-master/world-generation) executable, never the player-facing
    turn processor this project otherwise reconstructs from. This is
    the first piece of real, sourced world-generation data this
    project has found (every previous phase's own "world generation
    has no surviving source" note was accurate for everything *else*
    -- province/feature placement, treasure assignment, rumor
    falsification -- just not, it turns out, this one specific table).
  - Positionally verbatim against `Monster`'s own 61-entry declaration
    order (`ROC`..`MERMAID`, then `NOMONSTER`); the Pascal array itself
    has 71 entries (61 real + the same 10 unused `em1`-`em10`
    extension slots this project already excludes everywhere else).
    `Monster.NOMONSTER` is also excluded from the resulting dict --
    its own array entry (`Tomb, Tomb`) is a degenerate positional
    filler for the "no monster" sentinel, not a real preference;
    nothing in the Pascal source ever assigns Nomonster to guard
    anything.
  - **Still not a full world-gen algorithm**: nothing here says how a
    *feature*'s own kind gets decided first, how many features a
    province gets, or how ties/randomness among several eligible
    guardian species for one feature type resolve -- a real, sourced
    building block for a future world-gen phase, not a complete
    answer. `models/feature.py`'s own docstring is updated to note
    this specific exception to its "no surviving source" world-gen
    claim, and its already-stale note about `Treasure` (fully built
    since Phase 77) is corrected too.
  - Non-breaking: full suite passed unchanged (1558 passed) before any
    new tests were written -- a new dict with no existing call sites.
    3 new tests added (1561 passed total) in `tests/test_feature.py`,
    covering full 60-species coverage (Nomonster correctly excluded),
    that every value is a real `FeatureType` pair, and known verbatim
    pairs.
- **Phase 80 (current)**: `models/alignment.py` -- confirms, completes,
  and one-character-fixes the `Alignment` enum against a real Pascal
  source found while continuing to mine `CTBOTH.PAS`, the same way
  Phase 79 found `MONSTER_GUARDED_FEATURE_TYPES`.
  - **`Alignment` was originally (Phase 4) transcribed from `Mostri.md`**
    (a parent-project game-design doc), not `CTBOTH.PAS` directly --
    its own docstring said so honestly from the start. This phase found
    the real source: `CTBOTH.PAS`'s `outlook` enum (`Heavenly, Good,
    Druidic, Worldly, Animal, Evil, Hellish, Undead, Mechanical,
    Special`) and its own `outname` display-string table (`'Divine',
    'Good', 'Druidic', 'Neutral', 'Pagan', 'Evil', 'Anti-Holy',
    'Undead', 'Mechanical', 'Special'`, positionally verbatim) --
    confirmed to genuinely mean "leader/kingdom alignment" (not a
    same-named unrelated concept) via `REPORTS.PAS`'s own
    `lalign[ldran]: outlook` ("leader alignment").
  - **The existing 7 `Mostri.md`-derived tags turned out to already
    match 7 of the 10 real `outname` strings almost exactly** --
    independent confirmation this project's earlier, non-Pascal-sourced
    guess was right, not a lucky coincidence uncovered too late to
    matter. The 3 real values it was missing (`UNDEAD`, `MECHANICAL`,
    `SPECIAL`) are added.
  - **One real discrepancy found and fixed**: `DRUID`'s own value was
    `"Druid"`; the confirmed Pascal string is `"Druidic"`. Corrected
    outright (not just flagged) after confirming, by direct grep, that
    nothing in this project's source or tests ever reads
    `Alignment.DRUID.value` or any other member's `.value` -- safe to
    change with no consumer impact.
  - **Enum member names deliberately not renamed to match Pascal's own
    ordinal identifiers** (`Heavenly`, `Worldly`, `Animal`, `Hellish`):
    `Alignment` is consumed across a dozen `turn/*` modules and as many
    test files by this point (fanaticism, battle orchestration,
    Challenge/Patrol/Pursue execution); this project's own member names
    already match the real **display strings**, which is what every
    actual consumer cares about, so renaming would touch a large
    surface area for zero behavioral change. `turn/strength.py
    FANATICISM_CHANCE.get(alignment, 0.0)` already defaults safely for
    any alignment it doesn't have a chance for, so the 3 new members
    needed no changes there.
  - Non-breaking: full suite passed unchanged (1561 passed) before any
    new tests were written -- confirmed no code path reads `.value` on
    any `Alignment` member, so the `DRUID` string fix changed no
    behavior either. 3 new tests added (1564 passed total) in a new
    `tests/test_alignment.py`.
- **Phase 81 (current)**: `models/office.py` -- the kingdom/King
  "office" (achievement-based rank/title) catalog, found continuing to
  mine `CTBOTH.PAS` for real, sourced data the same way Phases 79 and
  80 found theirs. 52-member `Office` enum (~line 249-260) plus
  `OFFICE_NAME` (`ofcname`), `OFFICE_MIN_POINTS` (`minpts`),
  `OFFICE_VALUE` (`ofcval`), and `OFFICE_ENABLED_BY_DEFAULT` (`ofcuse`,
  all three tables `{$IFDEF Moderator}`, world/scoring-side only).
  - **Confirmed to be `PROSE.TXT`'s own documented `"$O"` marker**:
    "$O: Office name ('World Emperor', 'Arch-Mage Palatine', etc.)" --
    both example strings PROSE.TXT itself gives are verbatim
    `OFFICE_NAME` entries here (`Office.EMPEROR`/`Office.MAGE`), not
    just a plausible-sounding match.
  - **A red herring found and ruled out while researching this**: a
    second, much smaller `office` enum (`Pope, Caliph, Shaman, Emperor,
    King, Duke, Prince, Notitle`) appears at `CTBOTH.PAS` ~line 1741,
    immediately after a comment banner reading `"****Not implemented
    yet:"` -- dead, never-compiled placeholder code. This project's own
    `models/kingdom.py Kingdom.king_title` (a move file's free-text
    king-title line, e.g. "Shaman" in the real `AK3__T1.K1` sample) is
    **not** connected to either `office` enum -- confirmed by checking
    whether any real sample's own king-title text appears in the real,
    active 52-member `OFFICE_NAME` list; it doesn't. `king_title`
    remains exactly what Phase 1 already documented: unparsed,
    unvalidated free text.
  - **Confirmed real usage** (`REPORTS.PAS` ~line 624-632, the only
    place in the available source that reads these tables): for each
    office except `NO_OFFICE`, gated by `OFFICE_ENABLED_BY_DEFAULT`
    (unless a newer game version), a kingdom's accumulated points for
    that office (`Ofc_Pts(...)`, not available in this project's source
    -- lives in the missing main program) are compared against
    `OFFICE_MIN_POINTS` -- meeting the threshold *and* ranking #1 among
    all kingdoms for that office (`Rank(...) = 1`) is what earns the
    King the right to display that office's name in his own turn
    report, printed via the `ioname.x2` prose file. `OFFICE_VALUE`
    feeds a separate points-decay formula
    (`ofcpoints[ofc] := ofcval[ofc] * (1.0 - reduct)`) whose own
    `reduct` term isn't traced further here.
  - **Explicitly out of scope**: the actual points-accumulation formula
    (`Ofc_Pts`) and cross-kingdom ranking (`Rank`) live in the missing
    main program, so nothing in this module can compute which office a
    real `KingdomState` currently holds -- a type/threshold catalog
    only, the same category of "real, sourced, but not a complete
    algorithm" as Phase 79's `MONSTER_GUARDED_FEATURE_TYPES`.
  - Non-breaking: full suite passed unchanged (1564 passed) before any
    new tests were written -- a new file with no existing call sites.
    10 new tests added (1574 passed total) in a new
    `tests/test_office.py`, covering full 52-count coverage across all
    four dicts and verbatim spot-checks including both PROSE.TXT
    example strings.
- **Phase 82 (current)**: `models/temper.py` -- the character temper
  (personality/disposition) enum, found continuing to mine `CTBOTH.PAS`
  the way Phases 79-81 found theirs. `temper = (Cowardly, Cautious,
  Brave, Berserk)`, the `{$IFNDEF Noble}` (AK-active) branch -- a
  different, 9-value `temper` plus a `trait` enum exist under the same
  declaration's `{$ELSE}` (Noble) branch, not modeled, matching this
  project's already-established "Normal (non-Noble)" target (see
  `turn/movement.py`'s own map-bounds comment).
  - **Confirmed real and actually used**: `RUMORS.PAS`'s own
    `$`-prefixed marker dispatch (the block `report/prose.py`'s own
    docstring already partially quotes) has `'T':
    WW(tempername[_temper])` -- an exact match for `PROSE.TXT`'s own
    documented `"$T: Temper name ('Berserk', 'Cautious', etc.)"`
    marker, both example strings verbatim `TEMPER_NAME` entries here.
    The same file also prints alignment and temper together in one
    character-description sentence, confirming the two are meant to
    describe a character side by side.
  - **Directly relevant to two previously-flagged gaps**: Hire's
    "required pay... depends on unmodeled per-Hero temper/race/
    alignment compatibility" and Trail's own spied-on-intelligence
    payload ("Actions, race, temper, alignment..." -- temper "doesn't
    exist on `LeaderState` at all"). This phase supplies the enum,
    closing the "no vocabulary at all" half of both gaps; neither
    gap's actual formula/logic is attempted here -- both "Not yet
    implemented" bullets below are updated to say so.
  - Non-breaking: full suite passed unchanged (1574 passed) before any
    new tests were written -- a new file with no existing call sites.
    4 new tests added (1578 passed total) in a new
    `tests/test_temper.py`, covering full 4-count coverage and both
    PROSE.TXT example strings verbatim.
- **Phase 83 (current)**: `models/weapon.py` -- the monster/character
  attack-weapon vocabulary, found continuing to mine `CTBOTH.PAS` the
  way Phases 79-82 found theirs. `weapon` enum (29 members, ~line 559)
  plus `RUMORS.PAS`'s own `wname` (weapon noun) and `whit` (attack
  verb) tables.
  - **Confirmed to be `PROSE.TXT`'s own documented `"$S"` marker**:
    "$S: Attack method ('Slashed', 'Fired', 'Thrust', etc.)" --
    `RUMORS.PAS`'s own `$`-prefixed marker dispatch resolves `'S'` by
    picking `whit[Bow]`/`whit[Sword]` for a *character* attacker (Fire
    Arrow vs. Melee) or `whit[mtrweap[_mtype]]`/`whit[mtweap1[_mtype]]`
    for a *monster* attacker -- confirming `Weapon.BOW`/`Weapon.SWORD`
    specifically as real, literally-referenced ordinals.
  - **A confirmed structural gap, not an oversight, found while
    researching this**: the actual monster-to-weapon assignment tables
    `RUMORS.PAS` reads, `mtrweap[_mtype]` (ranged) and
    `mtweap1[_mtype]` (melee), matching the `mweaps` *type*
    `CTBOTH.PAS` itself declares, are used but **never declared
    anywhere in the available source** (checked `CTBOTH.PAS`,
    `RUMORS.PAS`, `REPORTS.PAS`, `DEF2.PAS`, `SAY.PAS`) -- the same
    category of gap as the missing main program. No
    `Monster`-to-`Weapon` mapping can be built from this; only the
    weapon vocabulary itself is modeled.
  - **`whit`'s own strings are themselves prose templates, not plain
    text**: several contain a live `/R` choice marker (e.g.
    `"slashed/Rclawed at"`) -- stored here as raw, unrendered source
    text, the same convention `models/treasure.py TREASURE_LABEL`
    (Phase 77) already uses for its own un-rendered strings.
  - Non-breaking: full suite passed unchanged (1578 passed) before any
    new tests were written -- a new file with no existing call sites.
    6 new tests added (1584 passed total) in a new
    `tests/test_weapon.py`, covering full 29-count coverage across both
    dicts, the confirmed Bow/Sword usage, and the live `/R` marker.
- **Phase 84 (current)**: `models/enums.py SPELL_NAME` -- `Spell`
  (Phase 23) finally gets real display names, found continuing to mine
  `CTBOTH.PAS` the way Phases 79-83 found theirs. `CTBOTH.PAS`'s own
  `spname` table (~line 677, 56 entries), confirmed to be `PROSE.TXT`'s
  own documented `"~: Spell name"` marker via `RUMORS.PAS`'s
  `Say(spname[_spell], spytype)`.
  - **All 35 real `Spell` ordinals (0-34) line up cleanly, positionally
    verbatim** -- including the 10 "secret" spells (25-34), which until
    now this project only ever cited by their Pascal identifier
    (`GATE_ANGEL`, `HEAL`, ...); `spname` gives their real display
    names for the first time (`HEAL` displays as "Words of Healing",
    for example).
  - **`NOSPELL` (35) deliberately excluded**, confirming a mismatch
    `Spell`'s own class docstring had already flagged from indirect
    evidence back in Phase 23: `spname[35]` is `"Extra Spell 1"`, not
    `"No spell"` -- the real `"No spell"` string sits at the table's
    very *end* (index 55), after the 20 unused `es1`-`es20` slots this
    project already excludes from `Spell` entirely. Directly confirms
    (rather than just infers) the docstring's own "stale-table
    authoring artifact" conclusion.
  - Non-breaking: full suite passed unchanged (1584 passed) before any
    new tests were written -- a new dict with no existing call sites.
    4 new tests added (1588 passed total) in a new
    `tests/test_spell_name.py`, covering full 35-entry coverage,
    Nospell's confirmed exclusion, and verbatim spot-checks including
    two of the newly-named secret spells.
- **Phase 85 (current)**: `turn/move_execution.py execute_move()` wires
  in the non-adjacent Move chase-step primitive Phase 78 built but
  didn't connect, closing that phase's own deferred "wiring" note.
  - **The chosen intermediate hex is, by construction, always adjacent
    to `current`** (it's one of `current`'s own neighbors) -- so
    `resolve_move()` itself needed **no changes at all**: it's simply
    called with the intermediate hex as its own target, exactly as if
    that had been the player's own literal order this phase. This is
    what makes exploration correct for a chase step: it's resolved
    against the *intermediate* hex's own real province data, never the
    ultimate target's, avoiding the wrong-terrain bug Phase 78's own
    note flagged as the reason wiring couldn't be a `resolve_move()`
    -only fix.
  - **`_classify_hex_ownership()`** feeds `step_toward_non_adjacent_target`'s
    `tier_of` callback from real `GameState` data: Owned/Allied via
    `state.is_allied()`, Enemy for an owned non-ally, Neutral
    otherwise -- `HexOwnershipTier.HERO_OWNED` is never produced,
    the same documented limitation Phase 78 already flagged
    (`ProvinceState` can't distinguish a Hero-ruled province from a
    genuinely wild one).
  - **`MoveExecutionResult` gains `reached_target`/`stopped_chasing`**:
    `reached_target` is a purely geometric fact (`actual_target ==
    target`, "was this phase's own hop the final one"), independent of
    whether the hop itself actually succeeds this phase.
    `stopped_chasing` is `True` -- with `exploration=None`, no cost, no
    relocation -- exactly when `step_toward_non_adjacent_target` itself
    returns `None`, quoting the rulebook's own "stop chasing" sentence
    verbatim. An enemy-occupied intermediate hex triggers a battle
    exactly like any ordinary Move -- the rulebook's chase-toward-target
    text doesn't address this case explicitly, so this project treats a
    chase step as mechanically identical to a directly-ordered Move to
    that same hex, a documented consistency choice, not a sourced
    special case.
  - **Multi-phase persistence still deliberately not wired in**: the
    rulebook's own sentence -- "The movement order will override orders
    in a subsequent phase only if the character is practicing in that
    phase" -- is read narrowly here (a documented interpretation, not
    the only possible one): an ongoing chase overrides *specifically* a
    later Practice order, not every other order type the way
    Pursue/Trail's own "for the rest of the turn" persistence (Phase
    70) blanket-preempts a leader's entire remaining plan. The broader,
    Pursue/Trail-style reading is also grammatically plausible from the
    rulebook's own wording alone; this project found no way to
    disambiguate it further from the available source, so wiring
    *either* interpretation into `turn/turn_processor.py` is deferred to
    a real follow-up phase -- mirroring the same primitive-now/
    wiring-later split Phase 66 and 70 already used for Pursue/Trail.
  - Non-breaking except one anticipated, fixed pre-existing test: full
    suite passed with exactly one already-updated failure before new
    tests were written -- `test_raises_for_unknown_target_province` had
    used a far-away, non-adjacent, data-free target as a proxy for "no
    province data," which now triggers chase resolution instead of an
    immediate raise; switched to a genuinely adjacent, data-free
    neighbor, which still hits the same immediate check exactly as
    before. 6 new tests added (1594 passed total) in
    `tests/test_move_execution.py`, covering the intermediate-hex
    landing, exploration resolving against the intermediate hex (not
    the target), a second hop reaching the target, the "stop chasing"
    case, the ownership-tier tie-break, and a battle triggered by an
    enemy-occupied intermediate hex.
- **Phase 86 (current)**: `turn/combat.py QUALITY_NAME` -- `Quality`
  (Phase 5) finally gets real display names, found continuing to mine
  `CTBOTH.PAS` the way Phases 79-84 found theirs. `CTBOTH.PAS`'s own
  `qname` table (~line 1283: `'Depleted','Green','Average','Veteran',
  'Crack','Elite'`), confirmed to be `PROSE.TXT`'s own documented
  `"^Q: Quality ('Average', 'Elite' etc.)"` marker via `RUMORS.PAS`'s
  own `WW(qname[_qual])`/`Say(qname[_qual], spytype)` -- both example
  strings verbatim entries here, and the table lines up exactly,
  positionally, with `Quality`'s own 6 ordinals (`DEPLETED=0`
  through `ELITE=5`).
  - Non-breaking: full suite passed unchanged (1594 passed) before any
    new tests were written -- a new dict with no existing call sites.
    3 new tests added (1597 passed total) in `tests/test_combat.py`,
    covering full 6-entry coverage and verbatim spot-checks including
    both PROSE.TXT example strings.
- **Phase 87 (current)**: `models/race.py RACE_NAME`/`RACE_ADJECTIVE`
  -- `Race` (Phase 4) finally gets real display names, found continuing
  to mine `CTBOTH.PAS` the way Phases 79-84/86 found theirs.
  `CTBOTH.PAS`'s own `rname`/`radj` tables (`rstrs` type, 23 entries
  each -- 15 real + 8 unused `er3`-`er10` extension slots, the same
  convention already used for every other enum's own unused tail).
  - **`radj[_race]` confirmed to be `PROSE.TXT`'s own documented
    `"$R: Race name ('Elven', 'Dwarven' etc.)"` marker** via
    `RUMORS.PAS`'s own `WW(radj[_race])` -- both example strings
    verbatim entries here. `rname[...]` is directly referenced too
    (e.g. `Concat('(a ', rname[lrace[ldr]], ' ', ...)'` -- "a Human
    warrior"), matching `PROSE.TXT`'s separate `"^R (): Race ('Humans',
    'Dragons', etc.)"` marker -- modeled here as the singular noun form
    `rname` actually stores, not a pluralized string.
  - Some `RACE_ADJECTIVE` entries diverge meaningfully from the plain
    noun (`RACE_NAME`): Dragons' own adjective is "serpentine", Eagles'
    is "feather-brained", Whales' is "aquatic" -- flavor text, not
    mechanical mistranscriptions, kept verbatim.
  - Non-breaking: full suite passed unchanged (1597 passed) before any
    new tests were written -- two new dicts with no existing call
    sites. 5 new tests added (1602 passed total) in a new
    `tests/test_race.py`, covering full 15-entry coverage for both
    dicts, both PROSE.TXT example strings, and the non-obvious
    adjective divergences.
- **Phase 88 (current)**: `models/enums.py FAME_DESCRIPTOR` -- a
  character-fame descriptor table, found while researching Phase 87's
  own `"^Y: Character Description"` marker. `PROSE.TXT`'s own example
  for `^Y` ("A Pagan, Berserk nature") turned out to be the *already-
  modeled* `Alignment`+`Temper` "nature/character" sentence
  (`RUMORS.PAS`'s own `Say(Concat(' ', outname[_align], ', ',
  tempername[_temper], ' nature/Rcharacter'), spytype)`), not new
  content -- but researching it surfaced a genuinely separate, real,
  unmodeled table: `RUMORS.PAS`'s own `Get_AbDesc` procedure (~line
  481), which builds sentences like "(a Human, famous for
  Necromancy)" from a character's *best* `Ability`'s own skill level.
  - `FAME_DESCRIPTOR: dict[int, str]` (10 entries, skill levels 0-9)
    transcribes its own `CASE` verbatim: "noted for" (0), "well known
    for" (1), "famous for" (2), "renowned for" (3), "world-famous for"
    (4), "revered for" (5), and "worshipped for" for the whole 6-9
    range -- confirmed a real Pascal `CASE lev OF 6..9:` range, not a
    transcription shortcut taken here. Confirmed real and used
    (`REPORTS.PAS` ~line 733 too, not just `RUMORS.PAS`'s own
    `Get_AbDesc` definition site).
  - Non-breaking: full suite passed unchanged (1602 passed) before any
    new tests were written -- a new dict with no existing call sites.
    3 new tests added (1605 passed total) in a new
    `tests/test_fame_descriptor.py`, covering full 0-9 coverage and the
    6-9 collapse.
- **Phase 89 (current)**: `turn/movement.py Direction`/`DIRECTION_NAME`
  -- `CTBOTH.PAS`'s own `dirname` table (~line 526, 6 entries, unlike
  most of this project's other transcribed enums there are no unused
  extension slots here), found continuing to mine `CTBOTH.PAS` the way
  Phases 79-84/86-88 found their own real data. This project's own
  `_EVEN_ROW_OFFSETS`/`_ODD_ROW_OFFSETS` (Phase 2) already *cited*
  `dirname`'s NE/E/SE/SW/W/NW ordering by comment to justify their own
  neighbor-offset order, but never transcribed the actual display
  strings until now.
  - **Confirmed to be `PROSE.TXT`'s own documented `"*: Direction"`
    marker** via `RUMORS.PAS`'s own `Say(dirname[_dir], spytype)`.
  - `Direction`'s own ordinal values (`NE=0` through `NW=5`) are
    deliberately declared in the exact same order as the pre-existing
    offset tuples, so the two stay in sync; purely additive, the
    offset tuples' own values are untouched.
  - Non-breaking: full suite passed unchanged (1605 passed) before any
    new tests were written -- a new enum/dict with no existing call
    sites. 4 new tests added (1609 passed total) in
    `tests/test_movement.py`, covering full 6-entry coverage, verbatim
    strings, and the ordinal alignment with the offset tuples' own
    order.
- **Phase 90 (current)**: `models/army_type.py ARMY_TYPE_NAME`/
  `ARMY_TYPE_DESIGNATION` -- `CTBOTH.PAS`'s own `atname`/`atdesig`
  tables (~lines 1288 and 1316, both positional with the `army` enum),
  found continuing to mine `CTBOTH.PAS` the way Phases 79-89 found
  their own real data.
  - **`ARMY_TYPE_NAME` confirmed to be `PROSE.TXT`'s own documented
    `"|: Army type name (\"Legion\", \"Fleet\" etc.)"` marker** via
    `RUMORS.PAS`'s own `Say(Concat(tms,' ',atname[_atype]),spytype)`.
  - **`ARMY_TYPE_DESIGNATION`** is a separate, shorter (9-char-max) form
    -- confirmed real and used via `REPORTS.PAS`'s own army-listing line
    (`atdesig` for the compact `"Skel <desig>"` skeletal-army case,
    `atname` for the normal case) and `SAY.PAS`'s own
    `astring:= atdesig[Mod_LAType(an)]`. `ArmyType.WHALES` diverges
    between the two (`'Whales'` vs `'League'`, from `whaleleague`'s own
    designator entry) -- a real quirk of the source table itself, kept
    verbatim rather than "corrected."
  - Both dicts cover exactly `ArmyType`'s existing 19 members; the
    `noarmy` sentinel and the `dinosaurs`/`vampires`/`marauders`/
    `ea3`-`ea20` extension slots are excluded, matching
    `ARMY_TYPE_BY_ORDINAL`'s own precedent (Phase 12).
  - Non-breaking: full suite passed unchanged (1609 passed) before any
    new tests were written -- two new dicts with no existing call
    sites. 5 new tests added (1614 passed total) in a new
    `tests/test_army_type.py`, covering full 19-entry coverage for both
    dicts, the PROSE.TXT example strings, verbatim designation samples,
    and the Whales name/designation divergence.
- **Phase 91 (current)**: new `models/discovery.py` -- the kingdom-level
  "Discoveries of the Sages" system, `CTBOTH.PAS`'s own `discovery` enum
  (~line 743, 64 members) plus **`CTME.PAS`'s own `dname` table** (~line
  4). This is the first phase to find real data in a Pascal file *other
  than* `CTBOTH.PAS` -- a prior phase's search for a `dname`/`_discov`
  pair came up empty because it only searched `CTBOTH.PAS` itself;
  broadening the search to the full available Pascal source (`CTME.PAS`,
  `YAK.PAS`, `SPEAK.PAS`, `AKT.PAS`, `TRANS.PAS`, alongside the four
  already-trusted files) surfaced it.
  - **Confirmed real and used** via `REPORTS.PAS`'s own "Discoveries of
    the Sages" kingdom report section (~line 325-348), whose own `CASE`
    statement also classifies the enum's four member groups into three
    effect categories: **ability skill bonus** (`fix0`-`fix9`,
    `wreck0`-`wreck9`, "+1 skill in \<ability\>"), **anti-spell ward**
    (`bild10`-`bild43`, "Anti-spell: \<spell name\>", covering `Spell`
    ordinals 4-19), and **revenue bonus** (`crunch0`-`crunch27`, "+X%
    revenue", X cycling 1-4). Documented in the module docstring,
    verbatim from the Pascal `CASE` statement, but deliberately **not
    implemented** here -- only the name vocabulary is modeled this
    phase, matching how `models/office.py`/`models/weapon.py` (Phases
    81/83) started with vocabulary before any mechanical wiring.
  - `Discovery`'s own 64 member names are derived from `DISCOVERY_NAME`'s
    own display strings (e.g. `LAND_SHIP`, `MITHRIL_CHAINMAIL`), not the
    Pascal source's internal `fix`/`wreck`/`bild`/`crunch` identifiers,
    which carry no rulebook-facing meaning of their own -- same
    convention `Weapon`/`Treasure` already established.
  - `discval` (`CTBOTH.PAS` ~line 766, also confirmed real via the same
    report loop) is documented as a pure display-order key, not modeled
    as data since it has no use outside that one print loop.
  - Non-breaking: full suite passed unchanged (1614 passed) before any
    new tests were written -- a new enum/dict with no existing call
    sites. 4 new tests added (1618 passed total) in a new
    `tests/test_discovery.py`, covering full 64-entry coverage, verbatim
    samples from each of the four groups, and every group boundary
    ordinal.
- **Phase 92 (current)**: new `models/magic_feature.py` -- the smaller
  magical landmark found *inside* a geographic `Feature` (a "crystal
  ball" inside a Pyramid, a "magic bell" inside a Temple, etc.).
  `CTME.PAS`'s own `magfeat` enum (~line 448, 21 members) and `mfname`
  table (~line 549), found the same way Phase 91's `models/discovery.py`
  was: continuing to mine the wider Pascal source beyond `CTBOTH.PAS`.
  - **Confirmed to be `PROSE.TXT`'s own documented `"$\\"` marker**:
    `$\\: Magic feature name ("crystal ball", "magic bell", etc.)` --
    `RUMORS.PAS`'s own `$`-prefixed marker dispatch resolves it via
    `Say(mfname[_magfeat],spytype)`; also referenced in `REPORTS.PAS` and
    `SAY.PAS`.
  - `MAGIC_FEATURE_NAME`'s own strings are raw, unresolved compound
    templates (`"<name>/F<alternate>"` / `"<name>/S<alternate>"`, e.g.
    `"Pool/FStream"`, `"Gas_Trap/SElectric_Trap"`) -- this `F`/`S` prefix
    convention is distinct from the already-confirmed `/R` choice marker
    and isn't resolved by any source read so far, so it's stored
    verbatim, matching how `models/weapon.py WEAPON_HIT_VERB` and
    `models/treasure.py TREASURE_LABEL` (Phases 77/83) already store
    their own raw template strings.
  - `MagicFeature.ITSELF`'s own `mfname` entry is the literal string
    `'&'`, not a normal name -- apparently a marker meaning "the
    containing `Feature` counts as its own magic feature" -- kept
    verbatim rather than guessed.
  - **Confirmed real but deliberately out of scope**: `CTME.PAS` also
    declares `mf1`/`mff` (two separate per-`FeatureType` magic-feature
    assignment tables) and `mfpow1` (`array[magfeat] of power`, `power`
    being `CTME.PAS`'s own rich effect-type enum: `NewSex, NewTemp,
    NewRace, UpSkill, ..., CastSpell, SageDisc, ...`). Which magic
    feature a given `Feature` actually has, and what visiting it does,
    needs real design work and is left to a real follow-up phase --
    matching how Phase 91 also stopped at vocabulary alone.
  - Non-breaking: full suite passed unchanged (1618 passed) before any
    new tests were written -- a new enum/dict with no existing call
    sites. 5 new tests added (1623 passed total) in a new
    `tests/test_magic_feature.py`, covering full 21-entry coverage, the
    PROSE.TXT marker confirmation, verbatim samples, and the `ITSELF`/`&`
    quirk.
- **Phase 93 (current)**: `models/discovery.py` extended with the full
  "Discoveries of the Sages" mechanics -- the user supplied
  `Discovery.txt`, a design document giving the flavor/mechanics
  paragraph for all 64 discoveries (Phase 91's own enum order), the first
  phase this project to work from a user-supplied source document rather
  than the Pascal source or the rulebook `.TXT`/`.AK` files.
  - Every one of the 64 `Discovery.txt` paragraphs cross-checks exactly
    against `REPORTS.PAS`'s own `CASE` statement (already quoted in the
    Phase 91 docstring) -- all 20 ability-bonus paragraphs name the same
    `Ability` the Pascal formula computes, all 16 anti-spell paragraphs
    describe an effect on the same `Spell` the Pascal formula computes,
    so **`DISCOVERY_ABILITY_BONUS`/`DISCOVERY_ANTISPELL_TARGET` are now
    doubly confirmed**, not a guess from either source alone.
  - **One real, explicitly-documented discrepancy** surfaced comparing
    the 28 revenue paragraphs against the Pascal formula's 1-2-3-4 cycle:
    `SPECTACLES` (`crunch20`) computes `1%` by formula, but `Discovery.txt`
    states "2% each gameturn" -- every other of the 28 entries matches
    exactly. `DISCOVERY_REVENUE_BONUS_PERCENT` follows the Pascal formula
    (the actual executable behavior of the original engine) for this one
    entry, with the discrepancy called out at the dict entry itself and
    in the module docstring -- not silently resolved either way, per this
    project's standing sourcing discipline.
  - Added `DISCOVERY_DESCRIPTION` (all 64 paragraphs, verbatim),
    `DISCOVERY_ABILITY_BONUS` (`dict[Discovery, Ability]`, the 20
    `fix`/`wreck` entries), `DISCOVERY_ANTISPELL_TARGET` (`dict[Discovery,
    Spell]`, the 16 `bild` entries), `DISCOVERY_REVENUE_BONUS_PERCENT`
    (`dict[Discovery, int]`, the 28 `crunch` entries). Still deliberately
    **not implemented**: applying any of this to actual gameplay (how a
    kingdom earns a `Discovery`, how the ability bonus stacks with
    `LeaderState.skills`, how the anti-spell wards modify
    `turn/cast_execution.py`) remains a real follow-up phase.
  - Non-breaking: full suite passed unchanged (1623 passed) before any
    new tests were written -- three new dicts with no existing call
    sites. 10 new tests added (1633 passed total) in
    `tests/test_discovery.py`, covering full coverage and non-overlap of
    all three mechanics dicts, cross-checking every ability-bonus entry's
    description text against its dict value, verbatim samples, the
    1-2-3-4 revenue cycle, and the Spectacles discrepancy.
- **Phase 94 (current)**: `models/weapon.py` extended with
  `MONSTER_RANGED_WEAPON`/`MONSTER_MELEE_WEAPON` -- **closes a gap
  `weapon.py`'s own docstring had explicitly documented since Phase 83**:
  "the actual monster-to-weapon assignment tables `RUMORS.PAS` reads --
  `mtrweap[_mtype]`/`mtweap1[_mtype]` -- are used but never declared
  anywhere in this project's available source." They *are* declared --
  in `CTME.PAS` (~line 60-88), the same file Phase 91's `Discovery` and
  Phase 92's `MagicFeature` also found real data in, not `CTBOTH.PAS`.
  The prior check simply hadn't looked there yet.
  - Confirmed real and used, exactly as `weapon.py`'s own docstring
    already stated: `RUMORS.PAS`'s own `Say(whit[mtrweap[_mtype]],
    spytype)`/`Say(whit[mtweap1[_mtype]],spytype)` and `WW(wname[
    mtrweap[_mtype]])`/`WW(wname[mtweap1[_mtype]])`.
  - Both Pascal arrays are declared for the *full* `monster` type (71
    slots: 61 real species + 10 unused `em1`-`em10` extension slots) --
    only the first 61 are transcribed, matching `models/monster.py
    Monster`'s own already-established range.
  - `Weapon.NO_WEAP` is the common case for `MONSTER_RANGED_WEAPON` (49
    of 61 monsters have no ranged attack at all) -- not a
    missing/unresolved value, a real "no ranged weapon" fact.
  - The module docstring's "confirmed structural gap" section is marked
    fixed with a strikethrough, per this project's usual changelog
    convention, rather than deleted outright.
  - Non-breaking: full suite passed unchanged (1633 passed) before any
    new tests were written -- two new dicts with no existing call sites.
    6 new tests added (1639 passed total) in `tests/test_weapon.py`,
    covering full 61-entry coverage for both dicts, verbatim samples, the
    `NOMONSTER` sentinel, and the real ranged/melee split count.
- **Phase 95 (current)**: new `models/power.py` -- the magical effect a
  "Magic Feature" (`models/magic_feature.py`, Phase 92) can trigger, and
  the condition gating whether it does. `CTME.PAS`'s own `power` enum
  (~line 434, 25 members) and `powco` enum (~line 543, 7 members), plus
  `YAK.PAS`'s own `powname`/`coname` display-name tables (~line 420-439)
  -- this resolves the `power` enum Phase 92's own docstring had already
  named but deliberately left undefined.
  - **Confirmed real and player-facing** via `YAK.PAS`'s own `Set_Event`
    procedure -- the actual code that fires a magic feature's effect when
    a character visits it -- which writes both display strings straight
    to the player's report file: `WRITE(playfile,powname[fpower])` and
    (inside the nested `Set_FCon` condition-check)
    `WRITE(playfile,coname[fpowcon])`.
  - `POWER_NAME`'s own strings read as compact, abbreviated labels (`"+"`,
    `"-"`, `"Cast "`, `"Orac/Align"`, capped at 17 chars), not full prose
    -- most likely printed alongside a separately-computed number (a
    skill delta, a gold amount) -- stored verbatim rather than expanded
    into a guessed full sentence.
  - **Two more confirmed-real findings, deliberately deferred**: `mfpow1`/
    `mfpowf` (`array[MagicFeature] of power`, a primary/decoy pair
    mirroring `mf1`/`mff`'s own split) and an entirely separate `comfeat`
    enum (27 members: `Seaweed, Whirlpool, Trees, Cliff, LavaPool,
    Stalacs, Mine, Quicksand, ...`) with its own three `array[FeatureType]
    of comfeat` tables (`cfs`, `cf1`, `cff`) -- mundane, non-magical
    decorative/hazard landmarks inside a `Feature`, structurally parallel
    to `MagicFeature` but never magical. Both left to a real follow-up
    phase, matching the module's own docstring.
  - Non-breaking: full suite passed unchanged (1639 passed) before any
    new tests were written -- two new enums/dicts with no existing call
    sites. 7 new tests added (1646 passed total) in a new
    `tests/test_power.py`, covering full coverage of both enums, verbatim
    samples, and the `PC_NONE` empty-string quirk.
- **Phase 96 (current)**: `report/turn_report.py render_magic_feature_discovery()`
  -- the first phase to mine the `PROSE/` `.X2` template files directly
  (rather than the Pascal source that names them), the same way Phases
  91/92/95 found real data outside `CTBOTH.PAS`. `HostAK/TP/PROSE/
  MAGFEAT.X2` is Search discovering (or not) a `models/magic_feature.py
  MagicFeature` inside the `Feature` being searched.
  - The file's header (`"20 1"`) parses via `parse_template_choices`
    (Phase 61) as 20 choices, 1 line each -- but the file has 21 real
    content lines. Line 1 is the "found nothing" sentence
    (`MagicFeature.NONE`); lines 2-20 are 19 *textually identical* "found
    a magic item" filler sentences (positionally corresponding to
    `MagicFeature` ordinals 1-19, but the sentence text never actually
    varies by which one) -- together exactly the header's declared
    20-line pool. Line 21, outside that pool, is a distinguished sentence
    for `MagicFeature.ITSELF` (ordinal 20) -- selected here directly on
    `magic_feature`, not via `pick_variant`.
  - `render_magic_feature_discovery()` substitutes `MAGIC_FEATURE_NAME`'s
    own raw string straight into the template's `$\` marker, unresolved
    -- `MAGIC_FEATURE_NAME` already documents these as raw, unresolved
    `/F`/`/S` compound templates (Phase 92), and they can't be resolved
    by routing back through `report/prose.py render()`'s own `/F`/`/S`
    support either: `render()`'s pipeline resolves choice markers
    **before** substituting placeholder values, so a marker arriving
    *inside* a substituted value is never revisited. A rendered sentence
    therefore still shows the raw `"Pool/FStream"`-style text at the
    substitution point -- a known, already-documented limitation carried
    forward, not silently mis-resolved.
  - No `rng` parameter, unlike every other `render_*` function in this
    module -- the source has no real variation to pick from here.
  - Non-breaking: full suite passed unchanged (1646 passed) before any
    new tests were written -- a new function with no existing call
    sites. 4 new tests added (1650 passed total) in
    `tests/test_turn_report.py`, covering the `NONE`/found-something/
    `ITSELF` cases and the raw unresolved `$\` substitution.
- **Phase 97 (current)**: `models/power.py MCOND_TEMPLATE`/
  `PCOND_TEMPLATE` -- `HostAK/TP/PROSE/MCOND.X2` and `PCOND.X2` (both
  header `"7 1"`), found continuing to mine the `PROSE/` `.X2` template
  files directly, the same way Phase 96 found `MAGFEAT.X2`. Both map
  exactly 1:1 to `PowerCondition`'s own 7 members.
  - `MCOND_TEMPLATE` is the in-character message an NPC/feature "speaks"
    once the condition is satisfied; `PCOND_TEMPLATE` is the
    out-of-character description of what the condition requires (e.g.
    printed up front alongside a magic feature's own power description).
    Both share the identical `PC_NONE` text (`"(No condition here.)"`)
    across both files -- confirming the positional alignment, not a
    coincidence.
  - Raw, unrendered prose templates -- matching how `WEAPON_HIT_VERB`/
    `TREASURE_LABEL`/`MAGIC_FEATURE_NAME` already store their own raw
    template text rather than a pre-resolved sentence. Not wired into
    any renderer this phase.
  - **More real `.X2` findings surfaced but deliberately deferred**:
    `SPDESC.X2` (25 templates, 1:1 with `Spell`'s own first 25 ordinals
    -- a Search Feature's "Cast Spell" power description), `ENCSPEC.X2`
    (15 templates, 1:1 with `CTME.PAS`'s own `intro` enum -- not yet
    modeled anywhere in this project -- the "how you arrived at this
    Feature" narrative), `RACE.X2` (13 templates tied to the Fanaticism
    mechanic `turn/battle_orchestrator.py` already implements, Phase 35),
    and `POWMSG.X2` (a much larger, 44-real-line file backing the full
    `Power` effect system, not yet mapped cleanly to `Power`'s own 25
    ordinals). Each is a real, standalone follow-up phase, not attempted
    here.
  - Non-breaking: full suite passed unchanged (1650 passed) before any
    new tests were written -- two new dicts with no existing call sites.
    6 new tests added (1656 passed total) in `tests/test_power.py`,
    covering full 7-entry coverage for both dicts, verbatim samples, and
    the shared `PC_NONE` text.
- **Phase 98 (current)**: `models/power.py POWER_DESCRIPTION`/
  `CAST_SPELL_FEATURE_DESCRIPTION` -- `HostAK/TP/PROSE/FPDESC.X2` and
  `SPDESC.X2`, confirmed real and confirmed *together* via `SAY.PAS`'s
  own `_EDesc` procedure (`FD('...fpdesc.x2',S_PCom,1001+ord(fpower))`
  always, then `FD('...spdesc.x2',S_PCom,1001+setval)` additionally when
  `fpower` is `CastSpell`/`AnsPrayer`) -- the same procedure whose
  neighboring `FD('...mcond.x2',S_PCom,1001+ord(fpowcon))` call
  independently confirms Phase 97's own `MCOND_TEMPLATE` indexing was
  correct.
  - `POWER_DESCRIPTION` (`FPDESC.X2`, header `"25 1"`) is 1:1 with
    `Power`'s own 25 ordinals -- the full plain-English sentence for what
    each power does, shown every time.
  - `CAST_SPELL_FEATURE_DESCRIPTION` (`SPDESC.X2`, also header `"25 1"`)
    is 1:1 with `Spell`'s own first 25 ordinals -- shown *additionally*
    only for `CastSpell`/`AnsPrayer`. 11 of the 25 entries read
    `"(Illegal: <name>)"` -- the game's own confirmation that spell can
    never actually be granted this way -- kept verbatim rather than
    filtered out.
  - The `CastSpell` entry's own raw byte (`\x01`) is transcribed as `^A`
    per `report/turn_report.py`'s own established source-notation
    convention for that exact control byte.
  - Both raw, unrendered prose templates, matching every other `*_NAME`/
    `*_TEMPLATE`/`*_DESCRIPTION` dict in this project. Not wired into any
    renderer this phase.
  - Non-breaking: full suite passed unchanged (1656 passed) before any
    new tests were written -- two new dicts with no existing call sites.
    5 new tests added (1661 passed total) in `tests/test_power.py`,
    covering full coverage of both dicts, verbatim samples, and the 11
    illegal-spell markers.
- **Phase 99 (current)**: new `models/intro.py` -- how a character
  arrives at / discovers a geographic `Feature`, the narrative "intro"
  scenario shown once before the encounter plays out. `CTME.PAS`'s own
  `intro` enum (~line 520, 15 members) plus `HostAK/TP/PROSE/ENCSPEC.X2`
  (header `"15 1"`, 15 templates).
  - **Weaker evidence than Phases 96-98, documented honestly rather than
    overstated**: every prior `.X2`-sourced phase confirmed its file via
    a literal `FD(...)`/`Say(...)` dispatch call site. For `ENCSPEC.X2`,
    no such call site exists anywhere in the 13 available library files
    -- `YAK.PAS`'s own `Set_Event` computes and populates the value
    (`fintro:= intro(ord(fintro1[ft]) + IRand MOD (...))`, from real,
    populated `fintro1`/`fintrof` range tables) but nothing observable
    ever reads it back -- the same "computed but no confirmed consumer"
    gap category as `comfeat`/`fcomfeat` (`models/power.py`'s own Phase
    95 docstring).
  - What *does* support the positional mapping: `ENCSPEC.X2`'s own
    declared choice count (15) matches `intro`'s own 15 members exactly,
    and every individual template's content specifically and
    unambiguously matches its corresponding Pascal identifier -- e.g.
    template 6 ("eased_down ... the stairs ... leading ... down") is
    `DownStairs`, template 13 ("swam ... into the &") is `Swim`. Stronger
    than a coincidental fit (every one of the 15 lines is distinct and
    on-point, unlike `MAGFEAT.X2`'s 19 identical filler lines), but still
    inferred from internal consistency, not a dispatch citation.
  - `Intro`'s own member names keep `CTME.PAS`'s own identifiers
    (`MONK`, `VALET`, `DOWN_STAIRS`, `SWIM`, ...) rather than deriving
    names from `INTRO_TEMPLATE`'s prose -- they're already meaningful
    English words, matching `Monster`/`Race`'s own precedent.
  - `fintro1`/`fintrof` (the per-`FeatureType` range tables that pick
    which `Intro` values are possible for a given Feature) are confirmed
    real but deliberately deferred, matching how `models/magic_feature.py`
    (Phase 92) deferred its own analogous `mf1`/`mff` tables.
  - Non-breaking: full suite passed unchanged (1661 passed) before any
    new tests were written -- a new enum/dict with no existing call
    sites. 5 new tests added (1666 passed total) in a new
    `tests/test_intro.py`, covering full 15-entry coverage, verbatim
    samples, and the distinct stair/water scenarios.
- **Phase 100 (current)**: `models/race.py RACE_FANATICISM_TITLE` --
  `HostAK/TP/PROSE/RACE.X2` (header `"13 1"`), confirmed real via
  `SAY.PAS`'s own `Check_BFace` procedure, the `_ARFan` branch:
  `FD('...race.x2',S_Batt,1001+trint)`, where `office(trint+ord(
  Humanking))` looks up that race's own "king" `Office` title
  (`Humanking`, `Elvenking`, `Dwarvenking`, `Orclord`, `Dragonlord`,
  `Eagleking`, `Whaleking`, ..., `Mermanking`, `Entking`, `Trollking`,
  `Wereking`) and `prevchar[...]` finds the character currently holding
  it. `trint` positionally matches `Race`'s own first 13 ordinals
  (`HUMAN`-`SAURIAN`), confirmed both by the exact count and by each
  entry's own content (`DWARVEN`: "King Under the Mountain", `MERMISH`:
  "Holy King of Atlantis", `ENTISH`: "Tsar of the Trees").
  - `NO_RACE`/`SAURIAN` are the empty string -- no "king" `Office` exists
    for either, a real fact rather than a missing value.
    `VAMPISH`/`ROHAN` have no entry at all, outside the file's own
    declared 13-choice range.
  - This is a **race-based** fanaticism narrative, distinct from (and
    not wired to) the already-implemented **alignment-based** roll
    (`turn/strength.py roll_fanaticism`, Phase 35) -- `Check_BFace`'s own
    surrounding `CASE` shows they're two of (at least) four sibling
    variants (alignment-based via `Good_Fan`/`Evil_Fan`, title-based via
    `GANG.X2`, race-based via `RACE.X2`), selected by a story-code value
    this project doesn't decode. Only the raw template data is
    transcribed here; wiring `_ARFan`'s own selection condition and
    `GANG.X2`'s sibling table are left to a real follow-up phase.
  - Non-breaking: full suite passed unchanged (1666 passed) before any
    new tests were written -- a new dict with no existing call sites.
    4 new tests added (1670 passed total) in `tests/test_race.py`,
    covering the 13-entry range, verbatim samples, the two blank
    entries, and the `VAMPISH`/`ROHAN` exclusion.
- **Phase 101 (current)**: `models/power.py POWER_CONDITION_REJECTION_MESSAGE`/
  `POWER_CONDITION_REJECTION_INTRO` -- `HostAK/TP/PROSE/POWMSG.X2`
  (header `"50 1"`) was this phase's original target (`SAY.PAS`'s own
  `_PowMsg` dispatches it: `FD('...powmsg.x2',S_PCom,1000+trint)`), but
  **investigation found it doesn't map cleanly to any enum this project
  models** -- the header declares 50 choices but only ~42 lines carry
  real distinct text, and individual entries read as unrelated
  situational messages (Oracle-of-Wealth errors, Gamble win/lose text,
  GrantWish success, NewSex flavor, RECHARGE errors, ...), each
  evidently hardcoded to its own specific `trint` value by call sites
  that live only in the missing main program. Modeling this as a formal
  dict would mean inventing an index scheme with no source -- explicitly
  not attempted, per this project's sourcing discipline, rather than
  guessed.
  - What *is* real and cleanly citable, found while investigating the
    same neighborhood of `SAY.PAS`: the `_NoMeet` procedure
    (~line 1266-1275), an **inline** (not `.X2`-sourced) `CASE fpowcon
    OF` dispatch with literal `Say(...)` messages for exactly 3 of
    `PowerCondition`'s 6 non-`PC_NONE` members (`SameAlign`, `NeedKing`,
    `GTurn`) -- `PayUp`/`DrainSkill`/`DrainCourage` have no case at all,
    correctly excluded rather than guessed at.
    `POWER_CONDITION_REJECTION_MESSAGE` transcribes these three;
    `POWER_CONDITION_REJECTION_INTRO` transcribes the one generic line
    said first regardless of which condition failed. Inline Pascal
    source is, if anything, stronger evidence than a `.X2` file guess.
  - Non-breaking: full suite passed unchanged (1670 passed) before any
    new tests were written -- two new constants with no existing call
    sites. 4 new tests added (1674 passed total) in
    `tests/test_power.py`, covering the 3-entry range, the excluded
    conditions, verbatim samples, and the intro line.
- **Phase 102 (current)**: `models/office.py GANG_TEMPLATE` --
  `HostAK/TP/PROSE/GANG.X2` (header `"28 1"`), confirmed real via
  `SAY.PAS`'s own `Check_BFace` procedure, the `_ATFan` branch:
  `FD('...gang.x2',S_Batt,1001+Rint-ord(Divineking))` -- a title-based
  fanaticism narrative, sibling to Phase 100's own `RACE_FANATICISM_TITLE`
  (both are branches of the same `Check_BFace CASE`).
  - The index is an `Office` offset counted *from* `DIVINE_KING`, not a
    separate enum -- confirmed real content sits at exactly `DIVINE_KING`
    (offset 0), `GOOD_KING` (1), `DRUID_KING` (2), `NEUTRAL_KING` (3),
    `PAGAN_KING` (4), `EVIL_KING` (5), `NECRO_MAGE` (6, blank -- not an
    alignment "king" title), `UNDEAD_KING` (7), and one isolated entry
    far later at `DUELLIST` (offset 22, "Imperial Musketeers"). Every one
    of these 9 positions independently confirms the exact `Office`
    ordinal arithmetic, since each entry's own content matches its
    computed title exactly (offset 4 explicitly names "the League of
    Pagan Clerics"; offset 22 lands precisely on `DUELLIST` and reads
    "Imperial Musketeers").
  - Only these 9 confirmed entries are transcribed. The large stretch
    between `UNDEAD_KING` and `DUELLIST` (`PLAINS_KING` through
    `ASSASSIN`, 14 slots) is blank in the source file too, but is
    **not** asserted here as confirmed empty-string data, unlike
    `RACE_FANATICISM_TITLE`'s own `NO_RACE`/`SAURIAN` (which sat inside a
    short, fully-populated 13-entry range, flanked immediately by real
    content on both sides) -- this stretch has no confirming context
    either side and is more likely simply unfinished content in the
    original file.
  - Non-breaking: full suite passed unchanged (1674 passed) before any
    new tests were written -- a new dict with no existing call sites.
    4 new tests added (1678 passed total) in `tests/test_office.py`,
    covering the 9-entry set, verbatim samples, the `NECRO_MAGE` blank,
    and the excluded unconfirmed middle stretch.
- **Phase 103 (current)**: `models/office.py OFFICE_PERK_DESCRIPTION` --
  `HostAK/TP/PROSE/IONAME.X2` (header `"60 1"`, 52 real content lines),
  the exact file `models/office.py`'s own pre-existing docstring had
  already cited (`FD('...ioname.x2', ..., 1001+ord(office))`), now
  actually transcribed.
  - Unlike `GANG_TEMPLATE`, this file has **full, gapless 1:1 coverage
    of all 52 `Office` members** -- only `NO_OFFICE`/`NO_TITLE` are
    blank, exactly the two sentinel members with no real title.
  - Every entry reads `"TITLE: perk description"`. The title half
    duplicates `OFFICE_NAME` (same text, different casing), so only the
    perk half -- the genuinely new information, a specific mechanical
    benefit holding that office grants (`"Recruit Extra Land Unit"`,
    `"50% Human Fanaticism"`, `"Double Plains Exploration Rate"`, ...) --
    is modeled as `OFFICE_PERK_DESCRIPTION`.
  - The title half also **independently cross-confirms two other
    already-transcribed tables at every one of their own populated
    positions**: `models/race.py RACE_FANATICISM_TITLE`'s race-king
    titles appear verbatim (`"SAVIOR OF HUMANKIND"`, `"FIRST ELDER OF
    ELVENKIND"`, ...), and `GANG_TEMPLATE`'s own alignment-king titles do
    too (`"DIVINE ARCHANGEL"`/Thunderbird, `"CAPTAIN OF THE IMPERIAL
    MUSKETEERS"`/`DUELLIST`) -- confirming both of those phases' own
    `Office` positional mappings were correct.
  - `Office.NECRO_MAGE` has real content here (`"Imp Familiar, 25% Magic
    Resistance"`) despite being `GANG_TEMPLATE`'s one blank gap -- no
    contradiction: `GANG.X2` is a separate, sparser file specific to the
    alignment-title fanaticism narrative, and simply has nothing at that
    one position.
  - Non-breaking: full suite passed unchanged (1678 passed) before any
    new tests were written -- a new dict with no existing call sites.
    5 new tests added (1683 passed total) in `tests/test_office.py`,
    covering full gapless 52-entry coverage, the two blank sentinels,
    verbatim samples, and the `GANG_TEMPLATE` cross-confirmation.
- **Phase 104 (current)**: `report/turn_report.py render_march()` --
  `HostAK/TP/PROSE/MARCH.X` (header `"3 1"`), confirmed real via
  `SAY.PAS`'s own `_LMarch` dispatch: `FD('march',S_Admin,3)` -- the Move
  action's own report line.
  - The `dex` parameter (`3`, matching the file's own 3 declared choices)
    is small enough to fall into `RUMORS.PAS FD`'s per-character-seed
    pseudo-random selection scheme, not the deterministic `1001+X`
    indexing every earlier `.X2`-sourced phase in this module used --
    confirmed by reading `FD`'s own body (`RUMORS.PAS` ~line 2288-2333):
    `dex < 100` routes through `fdcode`/`fdinc`/`Good_Inc`, the same
    unrecoverable "story-code bytecode log" `pick_variant()`'s own
    docstring already flagged for `CONQ.X`/`SPY.X` (Phase 63).
    `render_march()` therefore reuses that same
    `parse_template_choices`/`pick_variant` infrastructure, not a new
    indexing scheme.
  - The raw `\x10` control byte in `MARCH.X`'s own text is `PROSE.TXT`'s
    `^P` marker ("Province number", e.g. `"0304"`) -- transcribed in
    source notation per this module's own established convention.
  - **More real, confirmed `.X`/`.X2` findings surfaced but deliberately
    deferred**, each needing more design work than this phase's scope:
    `SNEAKUP.X`/`FLEEFAIL.X` (Steal/Flee maneuver failure -- confirmed,
    but each needs a trailing `CASE`-selected completion clause this
    project doesn't model yet), `RWENC.X` (a "random encounter while
    traveling" narrative), `TACTICS.X2` (a 9-level tactical-superiority
    bucket, `FD('...tactics.x2',S_Batt,Max(1001,Min(1009,1000+battac)))`
    -- structurally analogous to this module's own `margin_bucket()`,
    but `battac`'s own formula isn't traced), `NEMESIS.X2` (real and
    dispatched via `_ANem`, but its own index `Rint` isn't a formula this
    project can trace, and the file's own content mixes recognizable
    `ArmyType` nemesis pairs with unmodeled monster types like
    "Dinosaurs", so no clean index scheme is asserted).
  - Non-breaking: full suite passed unchanged (1683 passed) before any
    new tests were written -- a new function with no existing call
    sites. 5 new tests added (1688 passed total) in
    `tests/test_turn_report.py`, covering all 3 variants, the `/S` sea
    marker, and the `^P` substitution.
- **Phase 105 (current)**: `report/turn_report.py render_flee_failure()`/
  `render_sneak_detected()` -- `HostAK/TP/PROSE/FLEEFAIL.X` and
  `SNEAKUP.X`, both confirmed real, found finishing the Phase 104
  investigation.
  - `FLEEFAIL.X` (header `"4 1"`) is dispatched via `SAY.PAS`'s own
    `_LCot: FD2('fleefail',S_PCom,3)`. `FD2` is a thin wrapper
    (`FD2(fn,spl,dex) = FD(fn,spl,dex+5*ord(_attl<>bestldr))`) that still
    routes through `FD`'s own `dex < 100` per-character pseudo-random
    scheme (Phase 104's own finding) regardless of the `+5` offset --
    `render_flee_failure()` reuses `pick_variant()` exactly like
    `render_march()`. Every template is a complete, self-contained
    sentence -- no trailing completion clause needed, unlike `SNEAKUP.X`.
  - `SNEAKUP.X` (header `"4 1"`) is dispatched via `_LSeen`:
    `FD('sneakup',S_PCom,7)`, immediately followed by a **separate**
    story-code read (`Rint`) selecting one of three literal completion
    clauses: `CASE Rint OF 0: Say(' melee range.',...); 1: Say(' bow
    range.',...); 2: Say(' spell range.',...); END;`. Every one of
    `SNEAKUP.X`'s own 4 templates ends mid-sentence with "at",
    confirming they're meant to be immediately followed by one of these.
    `render_sneak_detected()` takes the completed clause as an explicit
    `range_suffix` parameter rather than guessing which of the three
    applies -- this project has no source for what decides melee/bow/
    spell range, the same caller-supplied-fact pattern as `is_sea`. The
    three confirmed clauses are exported as `SNEAKUP_RANGE_MELEE`/
    `SNEAKUP_RANGE_BOW`/`SNEAKUP_RANGE_SPELL` rather than inventing a new
    enum with no Pascal source of its own.
  - Non-breaking: full suite passed unchanged (1688 passed) before any
    new tests were written -- two new functions with no existing call
    sites. 9 new tests added (1697 passed total) in
    `tests/test_turn_report.py`, covering all variants of both
    functions, the `/S`/`^A` markers in `FLEEFAIL.X`, and all three
    range-suffix completions in `SNEAKUP.X`.
- **Phase 106 (current)**: `report/turn_report.py
  render_wandering_encounter()` -- `HostAK/TP/PROSE/RWENC.X` (header
  `"4 1"`), confirmed real via `SAY.PAS`'s own `_LWEnc` dispatch:
  `BEGIN randlevel:= 1; FD('rwenc',S_Adv,3); END;` -- the opening/intro
  sentence for stumbling into a wandering encounter while traveling,
  distinct from Search's own `models/intro.py Intro` (Phase 99, which is
  specifically about discovering a geographic `Feature`, not a chance
  meeting on the road). `dex=3` again falls into `FD`'s own `dex < 100`
  pseudo-random scheme (Phase 104's own finding), so
  `render_wandering_encounter()` reuses `pick_variant()` the same way
  `render_march()`/`render_flee_failure()` do.
  - ~~A larger, real "wandering/patrol encounter outcome" system was
    found alongside it, deliberately left out of scope: `SAY.PAS`'s own
    `_LPass`/`_LBefr`/`_LTricks`/`_LDense`/`_LDona`/`_LHear`/`_LNice`/
    `_LGreet` are plain, non-`.X`-sourced `Say(...)` calls describing
    what happens *after* the RWENC.X opening. Modeling that whole
    outcome tree is a real, standalone follow-up phase.~~ Fixed in
    Phase 108 (`models/local_encounter.py`). `_LEnc`/`_LSafe`/`_LPEnc`
    dispatch their own sibling `.X` files (`enco.x`, `safpat.x`,
    `patenc.x`) for closely related encounter variants (`_LPEnc` sets
    `randlevel:= 2` instead of RWENC's `1`, suggesting a distinct
    danger-level tier) -- fixed in Phase 107 below.
  - Non-breaking: full suite passed unchanged (1697 passed) before any
    new tests were written -- a new function with no existing call
    sites. 5 new tests added (1702 passed total) in
    `tests/test_turn_report.py`, covering all 4 variants and the `/S`
    sea marker.
- **Phase 107 (current)**: `report/turn_report.py
  render_generic_encounter()`/`render_patrol_release()`/
  `render_patrol_encounter()` -- `ENCO.X`, `SAFPAT.X` and `PATENC.X`,
  the three sibling `.X` files found alongside `RWENC.X` in Phase 106,
  all confirmed real via `SAY.PAS`'s own dispatch.
  - `ENCO.X` (header `"1 1"`, `_LEnc: FD('enco',S_Adv,1)`) is the
    simplest possible encounter opening, a single template.
  - `SAFPAT.X` (header `"3 1"`, `_LSafe: FD('safpat',S_Adv,1)`) is
    getting caught but then released (a convincing official seal, an
    impressed judge, not actually being on a wanted list).
  - `PATENC.X` (header `"4 1"`, `_LPEnc: BEGIN FD('patenc',S_Adv,4);
    randlevel:= 2; END;`) is a more dangerous patrol/bounty-hunter
    encounter (beaten and tracked down, challenged as a suspected spy,
    killed a rogue in a duel only for his kin to come seeking revenge).
  - All three `dex` values fall into `FD`'s own `dex < 100` pseudo-random
    scheme (Phase 104's own finding), so every function here reuses
    `pick_variant()`. The raw `\x0b` control byte both `SAFPAT.X` and
    `PATENC.X` carry is `PROSE.TXT`'s own `^K` marker ("King name and
    title"), transcribed in source notation.
  - Non-breaking: full suite passed unchanged (1702 passed) before any
    new tests were written -- three new functions with no existing call
    sites. 8 new tests added (1710 passed total) in
    `tests/test_turn_report.py`, covering all variants of all three
    functions, including the `^K`/`^A` marker resolution.
- **Phase 108 (current)**: `models/local_encounter.py` -- the
  "Local Encounter Table" gap Phase 106 flagged and deliberately left
  open, now closed. Models the 10 confirmed `SAY.PAS` `Imp_Code`
  branches (`_LHearInv`/`_LPass`/`_LBefr`/`_LTricks`/`_LDense`/
  `_LDona`/`_LHear`/`_LNice`/`_LGreet`/`_LHearPat`, lines 458-459 and
  906-913) as `LocalEncounterEvent` (a new enum, using the real integer
  story-code values declared in `RUMORS.PAS`'s own `CONST` block --
  `_LPass = 3310` etc., ~lines 86, 118-121, 140 -- not made-up
  ordinals) plus `LOCAL_ENCOUNTER_TEMPLATE`, a raw-template dict in the
  same style as `models/intro.py INTRO_TEMPLATE`/`models/power.py
  POWER_DESCRIPTION` (no wrapper `render_*` function, since -- unlike
  the `FD(...)`-dispatched `.X` files -- each of these 10 codes carries
  exactly one confirmed literal `Say(...)` template, no per-code
  variant list to pick from).
  - Stronger evidence than `models/intro.py Intro` (Phase 99): here
    both the named constant *and* its dispatched content are directly
    confirmed in source, not just a positional/content-only match.
    What's still unconfirmed and not guessed at: which game-state fact
    picks one of these 10 codes over another for a given encounter (the
    selection logic lives in the missing main program).
  - Raw byte inspection (not just a printed preview) found real control
    -byte markers in 2 of the 10 templates: `_LHearInv` ends in `\x13`
    = `^S` ("Province name #2", the invaded province); `_LDona`
    contains `\x0b` = `^K` ("King name and title") immediately followed
    by a Pascal-escaped `''` (`^K's`); `_LHear` contains
    `\x01 & \x02\x06 \x05` = `^A & ^B^F ^E` -- `^B`/`^E` is
    `PROSE.TXT`'s own "excluded from the General Intelligence Reports
    of other players" span, a marker `report/prose.py`'s own docstring
    already documents and defers (King-exclusion markers, needing the
    full narrator-perspective system) -- transcribed here verbatim,
    left for the caller to supply literal values for, not resolved.
  - Non-breaking: full suite passed unchanged (1710 passed) before any
    new tests were written -- a new module with no existing call sites.
    10 new tests added (1720 passed total) in
    `tests/test_local_encounter.py`, covering every member's real
    `RUMORS.PAS` integer value, verbatim template samples, the
    `^K`/`$a`/`^B`/`^E`/`^F`/`^S` marker transcription, and rendering
    two templates end-to-end through `report/prose.py render()` with
    scoped values.
- **Phase 109 (current)**: `report/turn_report.py
  tactical_margin_bucket()`/`render_tactical_comparison()`/
  `NEMESIS_TEMPLATE` -- revisits `TACTICS.X2`/`NEMESIS.X2`, both
  confirmed real and dispatched since Phase 106 but deliberately left
  unmodeled at the time (`SAY.PAS _BTac`/`_ANem`, ~lines 1058-1064 and
  1084, immediate siblings of `_BLuck`/`_CLuck` in the same `Imp_Code`
  block already read for `_BRes`/`margin_bucket()`).
  - ~~`TACTICS.X2` ... `battac`'s own formula isn't traced~~ Closed:
    reading all 9 of `TACTICS.X2`'s own templates end to end (header
    `"9 1"`, exactly 9 real lines) reveals a **confirmed, monotonic
    9-point spectrum** -- template 1 is total advantage for the
    defender, template 5 ("neither leader could gain a tactical
    advantage") is dead even, template 9 is total advantage for the
    attacker, and `_BTac`'s own `battac < 5`/`battac > 5` comparisons
    confirm 5 is the intended midpoint. `tactical_margin_bucket()`
    reuses this confirmed scale (still a documented, unsourced bucketing
    *input*, the same precedent `margin_bucket()` already established
    for `bres`), fed by `turn/battle_line.py`'s own real
    `attacker_tactical_ability`/`defender_tactical_ability` (rulebook
    [7.2]). `battac`'s own formula is still not traced -- nor is the
    "but/also" clause `_BTac` prefixes this with, driven by a second
    unconfirmed replay value (`batluck`).
  - `NEMESIS.X2` (header `"100 1"`, only 15 of 100 declared choices
    populated) is modeled more conservatively: `NEMESIS_TEMPLATE` stores
    all 15 real lines verbatim, keyed only by their own raw file
    position -- no `ArmyType`-keyed lookup, no `render_*` wrapper.
    Cross-checking against `models/army_type.py`'s own rulebook-sourced
    `NEMESIS` dict finds unmistakable content matches for 7 of the 15
    lines (Phalanx/Legion, Legion/Heavy Cavalry, Light+Heavy
    Cavalry/Chariots, Light+Heavy Cavalry/Beasts, Warg Riders/Eagle
    Wing, Whales/Mermen, Trolls+Ents/Axemen) -- strong supporting
    evidence this is the genuine battle-nemesis narrative table, not a
    coincidence. 3 candidate lines (8, 9, 11) all point to the same 3
    `ArmyType`s' shared `Bowmen` nemesis with no further textual
    distinction, and 2 lines (2, 15) name an unmodeled "Dinosaurs"/
    "Sauropods" type -- so `Rint`'s own dispatch formula and a full
    index-to-`ArmyType` mapping both remain unasserted, per this
    project's sourcing discipline.
  - Non-breaking: full suite passed unchanged (1720 passed) before any
    new tests were written -- new functions/data with no existing call
    sites. 15 new tests added (1735 passed total) in
    `tests/test_turn_report.py`, covering the bucket-clamping boundary
    cases, three confirmed buckets' exact rendered text (including the
    `/S` sea marker), and `NEMESIS_TEMPLATE`'s real entry count plus two
    rulebook-cross-confirmed samples.
- **Phase 110 (current)**: `report/turn_report.py
  render_explore_progress()`/`render_explore_continued()`/
  `render_explore_already_maxed()`/`EXPLORE_NOT_PRESENT_PREFIX` -- the
  Explore action's own report family, found scanning the wide
  `_LDies`..`_LTreas` (3000-3063) stretch of `RUMORS.PAS`'s story-code
  `CONST` block for the first time (this module had so far only mined
  the 3300+ "encounter table" stretch). The first `.X`-sourced
  narrative in this module that pairs with an already-modeled, already
  -numeric game mechanic (`turn/exploration.py resolve_explore()`'s own
  `ExploreResult.new_percent`, Phase 3) rather than being purely
  decorative.
  - `_LExpImp: FD('expmove',S_Adv,0)` -> `EXPMOVE.X` (header `"6 1"`, 6
    real templates): the Explore action's own progress report, for a
    dedicated Explore.
  - `_LExpCo: FD('coexp',S_Red,1)` -> `COEXP.X` (header `"6 1"`, 6 real
    templates): the same progress report phrased as exploration gained
    *while marching* -- ties to `turn/move_execution.py`'s own already
    -modeled "Move's partial-exploration side effect" (also Phase 3).
  - `_LExpMax`/`_LExpDiff`: two more real, single, hardcoded `Say(...)`
    templates (no file) -- "already fully explored"
    (`EXPLORE_ALREADY_MAXED_TEMPLATE`, maps to `ExploreResult
    .fully_explored` already `True`) and a precursor clause for when
    the exploring character wasn't actually in the target province
    (`EXPLORE_NOT_PRESENT_PREFIX`, no trailing period -- a bare string
    constant the caller concatenates, the same choice
    `POWER_CONDITION_REJECTION_INTRO` established in Phase 101).
  - `_LExpFail`: confirmed real in the `CASE` (`SAY.PAS` line 453) but
    is a literal empty statement (`;`) -- produces no text at all,
    documented rather than modeled as a function.
  - `_LExpAtt` (3002): declared in `RUMORS.PAS`'s own `CONST` block but
    has no dispatch anywhere in `SAY.PAS` -- an orphaned constant, not
    pursued.
  - Both `EXPMOVE.X` and `COEXP.X` wrap their own "...% has been
    explored" clause in the `^B`/`^E` King-exclusion span
    (`PROSE.TXT`'s "excluded from the General Intelligence Reports of
    other players") -- the same already-documented, deferred marker
    `models/local_encounter.py HEAR_OF_FEATURE` used in Phase 108. Both
    files' `dex` (`0`/`1`) is `< 100`, so both render functions use
    `pick_variant()` per the established `FD` litmus test.
  - Non-breaking: full suite passed unchanged (1735 passed) before any
    new tests were written -- new functions with no existing call
    sites. 9 new tests added (1744 passed total) in
    `tests/test_turn_report.py`, covering both files' possessive/sea
    marker resolution and the two hardcoded templates verbatim.
- **Phase 111 (current)**: `report/turn_report.py
  render_move_to_bow_range()`/`render_move_to_melee_range()`/
  `render_fire_arrow_attack()`/`render_attack_missed()` -- the Fire
  Arrow attack sequence, continuing the 3000-3099 stretch of
  `RUMORS.PAS`'s story-code `CONST` block. Ties directly to
  `turn/encounter.py`'s already-modeled Fire Arrow combat
  (`roll_fire_arrow_attack()`, Phase 48), the same way Phase 110 tied
  Explore's own narrative to `resolve_explore()`.
  - `_LToBow: FD2('gobow',S_PCom,2)` -> `GOBOW.X` (header `"3 1"`, 3
    real templates): closing to bow range.
  - `_LToMel: FD2('gomel',S_PCom,3)` -> `GOMEL.X` (header `"3 1"`, 3
    real templates): closing to melee range, modeled for symmetry with
    `GOBOW.X`. Its own attack-action sibling (`_LSwing:
    FD2('swangat',S_PCom,3)` -> `SWANGAT.X`, 11 real templates,
    confirmed real while researching this phase) is left for a
    Melee-combat follow-up, not modeled here.
  - `_LFArr: FD2('farr',S_PCom,4)` -> `FARR.X` (header `"6 1"`, 6 real
    templates): the Fire Arrow attack action itself. Carries `\x01`
    (`^A`, article) and `\x17` (`^W`, `PROSE.TXT`'s "Striking weapon"
    marker) alongside `$S` (`PROSE.TXT`'s "Attack method" marker) --
    `render_fire_arrow_attack()` hardcodes `$S`="Fired"/`^W`="arrow"
    since this file is unambiguously always about firing an arrow.
    Every template ends without punctuation, mid-sentence -- the same
    "no trailing punctuation, caller concatenates" shape `_BClash`/
    `_BRes` already established (Phase 61).
  - `_LMisses: FD2('andmiss',S_PCom,5)` -> `ANDMISS.X` (header `"5 1"`,
    5 real templates): the miss continuation clause, confirming the
    concatenation shape (every line starts with a leading space, no
    capital letter). `render_attack_missed()` takes `weapon` as an
    explicit parameter (not hardcoded) since this file is shared by
    both `_LFArr` and `_LSwing` -- a future Melee-combat phase can
    reuse it unchanged.
  - `_LInfl`/`_LDevast`/`_LMortB` (hit/overkill/mortal-wound
    continuations, real and dispatched immediately alongside
    `_LMisses`) are confirmed real but deliberately not modeled this
    phase -- scoped to exactly the four codes requested.
  - Non-breaking: full suite passed unchanged (1744 passed) before any
    new tests were written -- new functions with no existing call
    sites. 10 new tests added (1754 passed total) in
    `tests/test_turn_report.py`, covering every function's variants,
    the `/S` sea marker, and the attack+miss concatenation forming one
    complete sentence.
- **Phase 112 (current)**: `report/turn_report.py
  render_attack_hit()`/`render_attack_devastating_hit()`/
  `render_mortally_wounded()` -- closes the `_LInfl`/`_LDevast`/
  `_LMortB` gap Phase 111 deliberately left open, completing the Fire
  Arrow attack sequence.
  - `_LInfl: FD2('andinfl',S_PCom,1)` -> `ANDINFL.X` (header `"5 1"`, 5
    real templates): the hit continuation clause, parallel in shape to
    `_LMisses`/`ANDMISS.X`. Carries `#` (`PROSE.TXT`'s "A number"
    marker) for the damage dealt, matching `turn/encounter.py
    roll_fire_arrow_attack()`'s own already-modeled return value.
  - `_LDevast: Say(' and devastated/Rannihilated [.',S_PCom)` -- a
    single, real, hardcoded template (no file), textually an obvious
    parallel to `_LInfl` and listed immediately next to it in
    `SAY.PAS`'s own `CASE` block. **Honestly flagged discrepancy**:
    `RUMORS.PAS` declares `_LInfl`/`_LMortB` at 3018/3019 but
    `_LDevast` at 3160, in the unrelated King-meeting/messaging
    stretch (`_LSay`/`_LKMeet` neighbors) -- Pascal `CASE` branches
    don't need constant-declaration order, so this doesn't contradict
    `_LDevast` being real, dispatched, combat-flavored content, but it
    does mean this project can't fully confirm it shares `_LInfl`'s own
    call site. Modeled regardless, with the discrepancy documented.
    This project has no source for what distinguishes an ordinary hit
    from a devastating one -- the caller decides which to render.
  - `_LMortB: FD2('mortwoun',S_PCom,5)` -> `MORTWOUN.X` (header
    `"4 1"`, 4 real templates): a **standalone** sentence (capitalized
    `[1`, complete on its own) appended *after* the attack+hit sentence
    rather than concatenated onto it. Its own 4th variant describes a
    stun, not a fatal wound, despite the file's own name -- transcribed
    verbatim, not smoothed over.
  - Non-breaking: full suite passed unchanged (1754 passed) before any
    new tests were written -- new functions with no existing call
    sites. 9 new tests added (1763 passed total) in
    `tests/test_turn_report.py`, covering every function's variants,
    the `/S` sea marker, the stun-not-death 4th `MORTWOUN.X` line, and
    the attack+hit concatenation forming one complete sentence.
- **Phase 113 (current)**: `report/turn_report.py render_melee_attack()`
  -- `_LSwing: FD2('swangat',S_PCom,3)` -> `SWANGAT.X` (header `"11 1"`,
  11 real templates), confirmed real while researching Phase 111 and
  deliberately deferred there; the Melee sibling to `_LFArr`/`FARR.X`
  (same "no trailing punctuation, caller concatenates" shape, meant to
  chain into `render_attack_missed()`/`render_attack_hit()`/
  `render_attack_devastating_hit()`, all already generic across attack
  types).
  - Uses `$S` (`PROSE.TXT`'s "Attack method" marker) but, unlike
    `FARR.X`, not `^W` (weapon) -- `render_melee_attack()` takes
    `attack_method` as an explicit caller-supplied parameter (e.g.
    `"Slashed"`, `"Thrust"`) rather than hardcoding one value, since a
    Melee weapon/verb genuinely varies by character, unlike Fire
    Arrow's fixed "Fired". 1 of the 11 templates uses a literal
    `assailed/attacked` verb choice instead of `$S` at all.
  - Two templates have real, slightly unusual phrasing kept as-is
    rather than "fixed": one never names the opponent via `[`, instead
    calling them "your fearsome enemy"; another writes `['s defenses`
    -- `[` immediately followed by a literal `'s` in the source text
    itself (not `PROSE.TXT`'s own `]` possessive marker).
  - No `/S` marker anywhere in this file (unlike `GOMEL.X`'s own
    movement-to-melee-range templates, Phase 111) -- no `is_sea`
    parameter. The raw `\x1a` byte at the file's very end is DOS's own
    end-of-file marker, stripped during transcription, not preserved
    as prose.
  - Non-breaking: full suite passed unchanged (1763 passed) before any
    new tests were written -- a new function with no existing call
    sites. 5 new tests added (1768 passed total) in
    `tests/test_turn_report.py`, covering variant selection, the `$S`
    attack-method substitution, and concatenation with
    `render_attack_missed()` forming one complete sentence.
- **Phase 114 (current)**: `report/turn_report.py
  render_hire_accepted()`/`render_hire_refused()`/
  `render_fire_hireling()`/`render_hire_counter_offer()` -- the
  Hire/Fire narrative (`SAY.PAS` ~lines 501-504), ties to
  `turn/hire_fire_decode.py`'s already-modeled `HireRequest`/
  `FireRequest` (Phase 17).
  - `_LHire: FD('acchire',S_Adv,6)` -> `ACCHIRE.X` (header `"1 1"`, 1
    real template): a successful Hire.
  - `_LHFail: FD('refhire',S_Adv,5)` -> `REFHIRE.X` (header `"3 1"`, 3
    real templates): a Hire refused over alignment enmity/disdain for
    the hiring King. Template 3's own raw text has a real, slightly odd
    authoring quirk kept verbatim: `for "Holding/R"Keeping ^A palace
    court...` -- the `/R` choice's right branch embeds its own literal
    opening quote mark alongside the word "Keeping".
  - `_LFire: FD('fireman',S_Adv,7)` -> `FIREMAN.X` (header `"4 1"`, 4
    real templates): a Fire.
  - `_LCounter: Say(...)` (sitting between `_LHFail` and `_LHire` in
    `SAY.PAS`'s own `CASE` block) -- a single, real, hardcoded template
    (no file) for a *different* Hire failure reason: a price rejection
    rather than an alignment one. `HIRE_COUNTER_OFFER_TEMPLATE`.
  - All four carry `\x0b` (`^K`, "King name and title") -- hiring/firing
    is always narrated in service of a King. `render_hire_accepted()`'s
    own single template still goes through `pick_variant()`, matching
    `ENCO.X`'s (Phase 107) "1-template file still uses pick_variant"
    convention.
  - Non-breaking: full suite passed unchanged (1768 passed) before any
    new tests were written -- new functions with no existing call
    sites. 8 new tests added (1776 passed total) in
    `tests/test_turn_report.py`, covering variant selection for all
    three `.X` files and the hardcoded `_LCounter` template verbatim.
- **Phase 115 (current)**: `report/turn_report.py` -- the ASpy report
  body (`SAY.PAS` ~lines 522-545, immediately after `_LSpy`'s own
  dispatch in the same `Imp_Code` procedure). **Closes a gap Phase 63's
  own docstring said didn't turn up anywhere** -- corrected there too.
  Every code here is a single, real, hardcoded `Say(...)` (no `.X`
  file), the line items `SPY.X`'s opening sentence introduces.
  - `_LSTax`: `"Approximate Taxation: #"` -- `render_spy_tax_estimate()`.
  - `_LSAT`: `"Province Army Type #: |"` -- `#` reads most naturally
    as a 1-based index enumerating one of the province's
    possibly-multiple recruitable Army Types. `render_spy_army_type()`.
  - `_LSList`: `"the following elements are present in @:  "` (real
    trailing double space, kept verbatim) -- the intro line for the
    detail lines that follow. `render_spy_elements_intro()`.
  - `_LSHere`: `"[ $ is here."` -- carries a bare `$` with **no
    `PROSE.TXT`-documented meaning** (every real `$`-prefixed marker is
    2 characters). Flagged honestly rather than guessed at (e.g.
    assumed to mean `$O`, Office name) -- `render_spy_character_here()`
    exposes it as an explicit `title` parameter defaulting to `""`.
  - `_LSNone`/`_LSNoCh`: two distinct negative-result lines (with vs.
    without forces mentioned). `render_spy_no_characters_or_forces()`/
    `render_spy_no_characters()`.
  - `_LSCap`: `"@ is the kingdom's capital province."` --
    `render_spy_capital_province()`.
  - `_LSEtc`: the report's own closing line, pointing further detail
    to the General Intelligence Report. `render_spy_report_closing()`.
  - `_LSLeads`/`_LSGarr`: `"[ leads approximately ^L^V."` / `"there is
    a garrison of approximately ^L^V."` -- both real. ~~Both genuinely
    blocked on `^L`, exposed as raw string constants only, no
    `render_*` wrapper.~~ Unblocked in Phase 118.
  - Non-breaking: full suite passed unchanged (1776 passed) before any
    new tests were written -- new functions with no existing call
    sites. 10 new tests added (1786 passed total) in
    `tests/test_turn_report.py`, covering every render function and
    the two blocked templates verbatim.
- **Phase 116 (current)**: `report/turn_report.py
  render_ally_proposed()`/`render_already_allied()`/
  `render_ally_refused()` -- the Ally/Treat narrative (`SAY.PAS` ~lines
  506-511, immediately after `_LFire` in the same `Imp_Code` block).
  - `_LAlly: FD('ally',S_Admin,8)` -> `ALLY.X` (header `"2 1"`, 2 real
    templates): a successful Ally proposal. Both `[3` and `[` refer to
    the same target King within a single template (e.g. template 1
    addresses `[3` in "urged `[3` to improve relations..." then names
    `[` again in "...accepted by `[`") -- both substituted with the
    same `king_name` value, not two different characters.
  - `_LATreat: Say('< treated with > ally [3.',S_Admin)` -- a single,
    real, hardcoded template (no file) for an *already-allied* notice
    (a repeat-turn "we already have a treaty" line, distinct from the
    first-time proposal `_LAlly` narrates). `render_already_allied()`.
  - `_LRefA` -- a single, real, hardcoded entry made of **two separate
    `Say(...)` calls** (no file) for a refused Ally proposal.
    `render_ally_refused()` concatenates both rendered sentences with
    no separator, matching every other multi-sentence entry already
    found in this module's own templates (e.g. `PATENC.X`'s own
    sentences directly abutting with no inserted space, Phase 107).
  - Non-breaking: full suite passed unchanged (1786 passed) before any
    new tests were written -- new functions with no existing call
    sites. 6 new tests added (1792 passed total) in
    `tests/test_turn_report.py`, covering both `ALLY.X` variants, the
    dual-marker substitution, and the no-separator concatenation.
- **Phase 117 (current)**: `report/turn_report.py
  render_take_gold()`/`render_inherit()`/`render_will()` -- the
  Treasure/Steal narrative (`SAY.PAS` ~lines 562-575 and 712),
  requested as `_LSteal`/`_LTakeG`/`_LInher`/`_LWill`.
  - `_LSteal` (3037) is declared in `RUMORS.PAS` but **has no dispatch
    anywhere in `SAY.PAS`** -- an orphaned constant, the same category
    as `_LExpAtt` (Phase 110). Only its `T_`/`G_`-prefixed siblings
    (`T_LSteal`/`T_MSteal`/`G_LSteal`/`G_MSteal`, a larger
    Steal-outcome cluster whose `T_`/`G_` prefix semantics aren't
    confirmed by any comment in the available source) are actually
    dispatched -- not pursued here, left for a future phase once that
    prefix distinction can be sourced rather than guessed.
  - `_LTakeG: FD('takeg',S_PCom,2)` -> `TAKEG.X` (header `"3 1"`, 3
    real templates): a successful gold theft.
  - `_LInher` has a real `IF _attl = _defl THEN ... ELSE ...` branch:
    the `THEN` branch was ~~genuinely blocked on `^L`~~, unblocked in
    Phase 118 (`render_inherit_as_heir()`). The `ELSE` branch is a
    single, clean, real template with one magic-item marker --
    `render_inherit()` still renders only that branch (the two
    situations are genuinely different, kept as two functions).
  - `_LWill`: the deceased's will being read, a single, real,
    hardcoded template (no file). The Pascal-escaped `''` (a literal
    apostrophe) is the same transcription convention `REFHIRE.X`
    already established (Phase 114).
  - `_MGain: Say('< took the ^L\.',S_PCom)` -- a single, real,
    hardcoded template (no file), also blocked on `^L` at the time,
    also unblocked in Phase 118 (`render_take_items()`).
  - Non-breaking: full suite passed unchanged (1792 passed) before any
    new tests were written -- new functions with no existing call
    sites. 8 new tests added (1800 passed total) in
    `tests/test_turn_report.py`, covering all three `TAKEG.X` variants,
    the confirmed `_LInher` ELSE branch, and both `_LWill` branches.
- **Phase 118 (current)**: `report/prose.py` gains its own `^L` list
  -insertion capability -- real design work, not transcription, closing
  a gap this project had found and deliberately left blocked *twice*
  (Phase 115's `_LSLeads`/`_LSGarr`, Phase 117's `_LInher` `THEN`
  branch and `_MGain`).
  - `render()`'s new `lists: dict[str, Sequence[str]] | None = None`
    keyword-only parameter maps the marker *following* `^L` (e.g.
    `^V`, `\`) to the caller-supplied sequence of strings to join.
    `^L<marker>` resolves to `PROSE.TXT`'s own quoted conjunction
    format -- comma-separated, no comma before the final item, `" and
    "` before the last one, matching the quoted example exactly
    ("241st Axemen, 34th Legion and 145th Fleet" for 3 items). 1 item
    renders bare; 2 items join as `"X and Y"`; 0 items raises
    `ValueError` (an empty list was never a real possibility in the
    original engine); a template needing `^L<marker>` with no matching
    `lists` entry also raises, naming the template -- the same "no
    sensible default" stance `/F`'s own missing-`feature_id` case
    already takes.
  - `^L` resolution runs as its own pipeline stage, right before the
    generic `values` substitution pass -- a `^L<marker>` pair is fully
    consumed as a unit; the same marker appearing elsewhere in the
    template on its own still resolves normally via `values`.
  - **Proved with 3 real consumers**, all in `report/turn_report.py`,
    no new template content or sourcing -- just closing gaps already
    found and documented: `render_spy_leads()`/`render_spy_garrison()`
    (Phase 115's own `_LSLeads`/`_LSGarr`) and
    `render_inherit_as_heir()`/`render_take_items()` (Phase 117's own
    `_LInher` `THEN` branch and `_MGain`).
  - Non-breaking: full suite passed unchanged (1800 passed) before any
    new tests were written. 16 new tests added (1816 passed total) --
    12 in `tests/test_prose.py` (single/two/three/four-item joins, the
    `PROSE.TXT`-quoted 3-item example, both marker shapes `^V`/`\`,
    both error cases, and that `^L` only consumes its own marker pair)
    plus 4 in `tests/test_turn_report.py` for the newly-unblocked
    renderers.
- **Phase 119 (current)**: `report/turn_report.py
  render_funeral_pyre()`/`render_steal_caught_and_ransomed()` -- two
  more real, hardcoded templates (no file) found alongside `_LInher`/
  `_LTakeG` while researching Phase 117, deliberately left unmodeled
  there.
  - `_LBurn: Say('] possessions were burned with [3 on the funeral
    pyre.',S_Priv)` (`RUMORS.PAS` `_LBurn = 3013`, immediately before
    `_LInher = 3014`) -- the deceased's own possessive (`]`) and a
    second character present at the pyre (`[3`, the same marker
    `ALLY.X`'s own target-King reference used, Phase 116).
  - `_LRans` (`RUMORS.PAS` `_LRans = 3039`, immediately after
    `_LTakeG = 3038`) -- a real entry made of two separate `Say(...)`
    calls (no file), narrating a failed Steal attempt: caught
    red-handed, then ransomed for half the thief's own treasury.
    `render_steal_caught_and_ransomed()` concatenates both rendered
    sentences with no separator, the same shape
    `render_ally_refused()` (Phase 116) already established.
  - Non-breaking: full suite passed unchanged (1816 passed) before any
    new tests were written -- new functions with no existing call
    sites. 3 new tests added (1819 passed total) in
    `tests/test_turn_report.py`.
- **Phase 120 (current)**: `report/turn_report.py
  render_defensive_march()`/`render_caught_up()`/
  `render_practice_tutored()`/`render_practice_already_maxed()` -- four
  more real, single, hardcoded templates (no file), each tying
  directly to an already-modeled `turn/*.py` mechanic rather than
  being purely decorative, the same "narrative for existing mechanics"
  pattern Phase 110 (Explore) and Phase 111 (Fire Arrow) established.
  - `_LCMarch` (`RUMORS.PAS` `_LCMarch = 3111`) -- a defensive Move
    (reinforcing a province under threat), distinct from `_LMarch`/
    `MARCH.X`'s own regular Move narrative (Phase 104). `^S` (Province
    name #2) is the origin province.
  - `_LCatch: Say('< caught up with [ in @.',S_Adv)` -- the
    Pursue/Trail catch-up moment itself, ties to
    `turn/pursue_execution.py`/`turn/trail_execution.py`
    (Phase 51/52/66/68).
  - `_LTeach: Say('< was tutored/Rinstructed in{ the art of} ^ by
    [.',S_Priv)` -- successful Practice tutoring, ties to
    `turn/practice_execution.py` (Phase 44/46).
  - `_LAlrMax` -- immediately follows `_LTeach` in `RUMORS.PAS`'s own
    `CONST` block, narrates `turn/practice_execution.py`'s own
    already-modeled max-skill-level rule.
  - Non-breaking: full suite passed unchanged (1819 passed) before any
    new tests were written -- new functions with no existing call
    sites. 9 new tests added (1828 passed total) in
    `tests/test_turn_report.py`.
- **Phase 121 (current)**: `report/turn_report.py
  render_commander_died_demoralized()`/
  `render_commander_fled_demoralized()` -- `_ADishK`/`_ADishF`
  (`RUMORS.PAS` `_ADishK = 3101`/`_ADishF = 3102`, sitting between
  `_LBenc = 3100` and `_LAssume = 3103`), both real entries made of
  two separate `Say(...)` calls (no file), narrating rulebook [7.1]'s
  "if the Supreme Commander is beaten... the losing side's forces...
  will become demoralized and... reduced in strength by 25%" -- the
  exact rule `turn/duel.py apply_duel_demoralization()` already
  models. Two narrative framings of the same mechanical event (the
  Supreme Commander's own defeat in the duel), not two different
  rules:
  - `_ADishK` -- the commander **died**.
  - `_ADishF` -- the commander was **cowardly/fled**.
  - This project has no source for which of the two narrations a
    given duel loss picks -- the caller decides, the same
    caller-supplied-fact pattern established throughout (`is_sea`,
    `range_suffix`, `weapon`). Both concatenate their two rendered
    sentences with no separator, matching every other multi-`Say()`
    entry already found in this module (Phase 107, 116, 119).
  - Non-breaking: full suite passed unchanged (1828 passed) before any
    new tests were written -- new functions with no existing call
    sites. 5 new tests added (1833 passed total) in
    `tests/test_turn_report.py`.
- **Phase 122 (current)**: `models/enums.py SPELL_CAST_ANNOUNCEMENT`
  -- a new 25-entry `dict[Spell, str]`, verbatim from
  `HostAK/TP/PROSE/SPNOTE.X2` (header `"25 1"`), discovered while
  investigating the user's own literal next request (the Ice-Suspend
  narrative cluster, `_LCIceS` et al.) -- `SAY.PAS`'s own `_LCIceS`
  case dispatches `Sps(Ice_Suspend, S_PCom)`, and `Sps(sp: spell; fam:
  integer)` (`SAY.PAS` ~line 241-242) is `FD('c:\tp\prose\spnote.x2',
  fam, 1001+ord(sp))` -- the same confirmed-strongest `dex >= 1000`
  deterministic-per-ordinal dispatch this project already established
  for `MAGFEAT.X2`/`MCOND.X2`/`IONAME.X2`, here newly confirmed for a
  dedicated `Sps()` helper rather than an inline `CASE`.
  - `SPNOTE.X2`'s 25 real templates have a gapless, individually
    content-confirmed 1:1 positional match to `Spell`'s own 25
    documented base spells (`RESURRECTION` = ordinal 0 through
    `MIRROR_IMAGE` = ordinal 24) -- the 10 undocumented "secret"
    spells (ordinals 25-34) have no entry, since the file itself stops
    at 25.
  - Several entries use `^L=` (Phase 118's list-insertion), matching
    `Sps()`'s callers that pass a family of affected characters (e.g.
    `Skeletal_Army`, `Plague`, `Flood`, `Tornado` -- all "the army/they
    arose/were struck/were slowed/were sucked up" narratives).
  - `_LCast1` (`SAY.PAS` lines 599-602), the opening clause these
    entries are meant to structurally follow via Pascal's own
    sequential `Say()` writes, is exposed as two bare constants
    (`CAST_SPELL_OPENING_COMPLETE_TEMPLATE`/
    `CAST_SPELL_OPENING_CONTINUED_TEMPLATE`) plus
    `CAST_SPELL_OPENING_COMPLETE_SPELLS` (the `{Tornado, Bless,
    Plague}` set that gets the complete-sentence variant, all others
    get the "...spell and " continuation) -- no wrapper function
    stitches them together, since the `CONTROL_UNDEAD` entry is itself
    genuinely truncated in the source (ends mid-word, "...mercilessly
    and_", no continuation anywhere in the file) and grammatical
    correctness of the concatenation was not independently verified
    for all 25 spells.
  - Non-breaking: full suite passed unchanged (1833 passed) before any
    new tests were written -- new data with no existing call sites. 7
    new tests added (1840 passed total) in
    `tests/test_spell_cast_announcement.py`.
- **Phase 123 (current)**: `report/turn_report.py` -- the full
  Ice-Suspend narrative cluster the user explicitly asked for
  (`_LBIce`/`_LFIce`/`_LPIce`/`_LIceCr`/`_LIceGh`/`_LShIce`/`_LWMelt`/
  `_LSFroz`, `SAY.PAS` lines 637-646, sitting immediately between
  `_LSIBers` and `_LUndWF`). Eight real, single, hardcoded templates
  (no file), each a distinct moment around `Spell.ICE_SUSPEND`'s own
  effect: cast (already `SPELL_CAST_ANNOUNCEMENT[Spell.ICE_SUSPEND]`,
  Phase 122) -> held in ice / breaks free -> fall damage or immunity
  -> stalemate options.
  - `render_ice_suspend_failed_to_hold()` (`_LPIce`) -- the ice fails
    to fully hold the target, who begins breaking free immediately.
  - `render_ice_break_out_attempt()` (`_LBIce`) -- the target's own
    break-out *attempt*.
  - `render_ice_break_out_success()` (`_LFIce`) -- the target's
    *successful* break-out.
  - `render_ice_fall_damage()` (`_LIceCr`) -- fall damage after the
    ice releases/shatters; `#` is `PROSE.TXT`'s own damage-points
    marker, the same convention `render_attack_hit()` (Phase 112)
    already established.
  - `render_ice_ghost_immune()` (`_LIceGh`) -- an incorporeal/
    ghost-type target is immune to the ice entirely.
  - `render_ice_immobilized()` (`_LShIce`) -- the immobilized *state*
    itself, distinct from the cast announcement.
  - `render_ice_wait_for_melt()` (`_LWMelt`) -- the opponent's own
    tactical choice not to attack a frozen target and wait it out.
  - `render_ice_steal_blocked()` (`_LSFroz`) -- a blocked Steal/
    Take-item attempt against a frozen target, using `report/prose.py`
    `^L` list insertion (Phase 118) over the `\` (Magic Item) marker,
    the same shape `render_take_items()` (Phase 118) already
    established.
  - No source ties these eight moments into one fixed sequence -- each
    is its own renderer, the caller sequences them according to the
    encounter's own real outcome, the same caller-decides-the-sequence
    stance already taken for `_ADishK`/`_ADishF` (Phase 121) and
    `_LCast1`/`SPELL_CAST_ANNOUNCEMENT` (Phase 122).
  - Non-breaking: full suite passed unchanged (1840 passed) before any
    new tests were written -- new functions with no existing call
    sites. 12 new tests added (1852 passed total) in
    `tests/test_turn_report.py`.
- **Phase 124 (current)**: `report/turn_report.py` -- the complete
  end-of-turn Financial Report every kingdom receives. `RUMORS.PAS`
  groups `_LRev = 3055`, `_LLCosts = 3056`, `_LACosts = 3057`,
  `_LFinance = 3058`, and `_LTreas = 3063` contiguously (with
  `_LCHoly`/`_LCHOD`/`_LCPsyBl`/`_LCInvis` -- already
  `SPELL_CAST_ANNOUNCEMENT` entries, Phase 122 -- interleaved at
  3059-3062); `_AUnpaid = 4013` sits in the separate "Army" 4000s block
  but is the same topical narrative (`SAY.PAS` lines 835-840, all five
  sentences physically adjacent). Five real, single, hardcoded
  templates (no file) -- the first narrative in this module tied to
  `GameState`'s own `KingdomState.treasury` field (Phase 9) and
  `turn/recruit_execution.py`'s own already-modeled treasury spending
  (Phase 15).
  - `render_finance_report_opening()` (`_LFinance`) -- the section's
    opening clause.
  - `render_finance_revenue()` (`_LRev`) -- this turn's revenue
    collected.
  - `render_finance_leader_costs()` (`_LLCosts`) -- leader upkeep
    cost.
  - `render_finance_unpaid_armies()` (`_AUnpaid`) -- percentage of
    armies that went unpaid; this project has no source for when this
    sentence is included versus omitted, so the caller decides whether
    to call it at all, the same stance `render_attack_devastating_hit()`
    (Phase 112) already established for its own conditional sentence.
  - `render_finance_army_costs()` (`_LACosts`) -- army upkeep cost.
  - `render_finance_treasury()` (`_LTreas`) -- the closing balance,
    ties directly to `KingdomState.treasury`'s own post-turn value.
  - No source stitches these five into one combined sentence --
    `SAY.PAS` dispatches each as its own `Say()` call in sequence, so
    each is its own renderer here too, matching the plain
    sequential-report shape already established for `render_spy_*()`
    (Phase 115).
  - Non-breaking: full suite passed unchanged (1852 passed) before any
    new tests were written -- new functions with no existing call
    sites. 6 new tests added (1858 passed total) in
    `tests/test_turn_report.py`.
- **Phase 125 (current)**: `report/turn_report.py` -- the
  Assassination narrative cluster. `RUMORS.PAS` groups `_AKill =
  3367`, `_ASeek = 3368`, `_AFail = 3369` contiguously (`SAY.PAS` lines
  958-970); `_LOAss = 3392` sits separately but is the same topical
  narrative (`SAY.PAS` line 958, immediately before `_ASeek`'s own
  block starts). Ties to `models/office.py`'s own
  `OFFICE_PERK_DESCRIPTION[Office.ASSASSIN] == "Free Assassination
  Attempt"` (Phase 103) -- the first narrative content confirming that
  perk's own real-game mechanic, even though no `turn/*.py` resolver
  executes an assassination attempt yet (the same
  narrative-precedes-execution stance already taken for the
  Ice-Suspend cluster, Phase 123, and the unexecuted personal-combat
  spells in `turn/cast_execution.py`).
  - `render_assassination_ordered()` (`_LOAss`) -- the order/directive
    itself.
  - `render_assassination_attempt()` (`_ASeek`) -- the attempt begins.
  - `render_assassination_success()` (`_AKill`) -- the attempt
    succeeds.
  - `render_assassination_failed()` (`_AFail`) -- the attempt fails, a
    real two-`Say()` entry concatenated with no separator, the same
    shape established throughout this module (Phase 107, 116, 119,
    121).
  - This project has no source for what determines success versus
    failure -- the caller decides, the same caller-supplied-fact
    pattern established throughout (`is_sea`, `weapon`,
    `_ADishK`/`_ADishF`).
  - Non-breaking: full suite passed unchanged (1858 passed) before any
    new tests were written -- new functions with no existing call
    sites. 7 new tests added (1865 passed total) in
    `tests/test_turn_report.py`.
- **Phase 126 (current)**: `report/turn_report.py` -- battle morale
  narrative plus a vampiric bite entry. `RUMORS.PAS` groups `_BSpeech
  = 4046`, `_BHome = 4047`, `_BNoDru = 4048`, `_BRWeap = 4049`,
  `_BBluff = 4050`, `_BNoEx = 4051` contiguously; `_BFun = 3326` and
  `_LChUnd = 3327` sit together in a separate, earlier block
  (`SAY.PAS` lines 1160-1188). Covers every real, hardcoded (no-file)
  entry from both groups; `_BNoDru`/`_BBluff` are file-dispatched
  (`NODRU.X`/`BLUFF.X`) and deliberately deferred.
  - `render_skeletal_army_fervor()` (`_BFun`) -- ties directly to
    `Spell.SKELETAL_ARMY` (already `SPELL_CAST_ANNOUNCEMENT`, Phase
    122).
  - `render_oratory_speech()` (`_BSpeech`) -- a real two-`Say()` entry
    concatenated with no separator (Phase 107, 116, 119, 121, 125),
    ties to `Spell.ORATORY` (Phase 122).
  - `render_homeland_defense_morale()` (`_BHome`) -- home-province
    defensive morale.
  - `render_weapon_rally()` (`_BRWeap`) -- a leader brandishes a magic
    item to rally troops; `^R` (Race name) is the first use of
    `models/race.py RACE_NAME` (Phase 87) inside this module, and the
    `the/R>` alternation (a marker embedded inside a `/R` choice) is
    resolved by `report/prose.py`'s existing `/R`-then-substitution
    pipeline exactly as documented -- no new engine capability needed.
  - `DUEL_NO_EXCUSE_TEMPLATE` (`_BNoEx`) -- a precursor clause (no
    trailing period), exposed as a bare constant with no wrapper
    function, the same shape `EXPLORE_NOT_PRESENT_PREFIX` (Phase 110)
    already established; ties to `turn/duel.py`'s own Duel-avoidance
    concept.
  - `render_vampiric_bite()` (`_LChUnd`) -- a vampiric bite that
    changes the victim's alignment; `$o` is the same Alignment/outlook
    -name marker `models/power.py` already uses (Phase 95/101).
  - Non-breaking: full suite passed unchanged (1865 passed) before any
    new tests were written -- new functions with no existing call
    sites. 10 new tests added (1875 passed total) in
    `tests/test_turn_report.py`.
- **Phase 127 (current)**: `report/turn_report.py` -- illegal-move
  error narrative. `SAY.PAS`'s main `Say_Code` `CASE` also dispatches
  on raw numeric codes outside `RUMORS.PAS`'s named 3000-9999
  story-code block -- `Say_Code` itself (`RUMORS.PAS` ~line 1685)
  confirms `code >= 32500` as a real, valid dispatch range, so codes
  `32500`/`32501` (`SAY.PAS` ~lines 1309-1325) are dispatched
  system/validation-error narratives, not orphaned CASE labels. Ties
  directly to two already-built validation mechanics:
  `turn/contested_province.py is_illegal_move_from_contested()` (Phase
  36) and the non-adjacent-move chase concept (Phase 78/85, rulebook
  [3.1]).
  - `render_illegal_move_non_adjacent()` (code `32500`).
  - `render_illegal_move_attempted()` -- code `32501`'s generic prefix
    (dispatched whenever `_next <> 5`), followed by one of four real
    sub-case sentences keyed by `_next`'s own range:
    `render_illegal_move_occupied_retreat()` (`_next = -1`),
    `render_illegal_move_insufficient_water_transport()` (`_next`
    100..149, keeps the source's own "insufficent" misspelling
    verbatim), `render_illegal_move_flooding_transport()` (`_next`
    150..199), `render_illegal_move_mermen_air_transport()` (`_next`
    200..249, keeps the source's own literal "air-transport" for
    Mermen rather than "correcting" it to "water-transport", the same
    honest-transcription stance already taken for `_LDevast`'s
    discrepancy, Phase 112).
  - The `ELSE` branch (`FD('c:\tp\prose\illmove.x2', ...)`) is
    file-dispatched and deliberately deferred pending `ILLMOVE.X2`
    extraction.
  - This project has no source for how the generic prefix and a
    specific sub-case sentence combine -- each is its own renderer,
    the caller composes them, the same caller-composes-the-sequence
    stance already taken for the Ice-Suspend (Phase 123) and
    Assassination (Phase 125) clusters.
  - Non-breaking: full suite passed unchanged (1875 passed) before any
    new tests were written -- new functions with no existing call
    sites. 6 new tests added (1881 passed total) in
    `tests/test_turn_report.py`.
- **Phase 128 (current)**: `models/advanced_ability.py` (new) --
  Advanced Abilities, the special talents gained above skill level 4
  in each of the 15 `Ability` categories, capped at level 9. **Source
  provenance, stated honestly**: this content was supplied directly by
  the user (a text file, "ABILITA SOPRA IL LIVELLO 4 OK.txt",
  2026-07-13) -- checked against every rulebook file in `Programma
  Pascal.zip` (`ADDEND.AK`, `RULES.AK`, `AKMAN.TXT`, `INFO.AK`,
  `TIPS.AK`) and found in **none** of them, so it's documented here as
  an external rulebook excerpt, not a Pascal-archive citation.
  - **Closes the `spdex` gap flagged since Phase 23**: `Spell`'s own
    docstring has said since Phase 23 that ordinals 25-34 (the 10
    secret spells) are "gated behind a specific special ability
    granted at skill 5+ (`CTBOTH.PAS`'s `spdex` lookup table)" with no
    further detail available from the Pascal archive. This excerpt's
    White/Necromancy/Elemental/Psychic/Illusion pools each contain
    exactly two "New spell" Advanced Abilities, and **all 10 match 1:1
    by name** against `SPELL_NAME` (Phase 84) for exactly `Spell`
    ordinals 25-34 -- direct confirmation the excerpt describes the
    same real system `spdex` implements, not an invented document.
    `ADVANCED_ABILITY_GRANTS_SPELL`.
  - **A second independent cross-check**: the "Gate Demon" spell's
    d100 demon table (7 entries) and the "Lava Pool" spell's
    monster-immunity list (29 entries) both name real creatures, and
    every single name matches an existing `models/monster.py Monster`
    member exactly (`MONSTER_NAMES`, Phase 75).
    `GATE_DEMON_TABLE`/`LAVA_POOL_IMMUNE_MONSTERS`.
  - `AdvancedAbility` (89 members, grouped by the 15 `Ability`
    categories in source order), `ADVANCED_ABILITY_POOL` (the
    random-draw pool per category -- sizes vary 5-8, **not** uniformly
    5-per-level: Thievery's own 8-candidate pool means a character can
    never gain every possible talent in that category),
    `ADVANCED_ABILITY_INTRO` (the per-category explanatory paragraph,
    e.g. what automatic per-level bonus gets discontinued),
    `ADVANCED_ABILITY_NAME`/`ADVANCED_ABILITY_TAGLINE`/
    `ADVANCED_ABILITY_DESCRIPTION` (title/short-tag/full-paragraph,
    verbatim from the excerpt).
  - This project has no source for the exact selection mechanic within
    a pool (uniform random over the remaining candidates? weighted?)
    -- deliberately left unmodeled; this phase only establishes the
    vocabulary/description data, the same scope precedent already
    established for `Discovery`/`MagicFeature`/`Weapon` (Phase 91-94).
  - Non-breaking: full suite passed unchanged (1881 passed) before any
    new tests were written -- new module with no existing call sites.
    16 new tests added (1897 passed total) in
    `tests/test_advanced_ability.py`.
- **Phase 129 (current)**: `report/turn_report.py` -- Monster Quest
  Fulfillment dialogue. `RUMORS.PAS` groups `_LFRaid = 3166` through
  `_LFRumor = 3193` contiguously (`SAY.PAS` lines 764-782) --
  direct-speech ("Sayeth...") dialogue between a quest-giving monster
  and the character trying to fulfill its quest, dispatched alongside
  the file-routed `_LSpake -> FULFILL.X2`/`_MReply -> MTALK.X2`/
  `_LRidAns -> RANS.X` (all keyed by `_qplotno`/`_qsubplot`, an
  unmodeled Quest-plot system -- narrative modeled independently of
  it, the same precedent already established for the Ice-Suspend
  cluster, Phase 123, and Assassination, Phase 125). Ties to
  `models/advanced_ability.py AdvancedAbility.DRUIDIC_TRADES`'s own
  "GI-ve" order description, which already covers the mechanical side
  of trading with a monster (Phase 128).
  - Marker convention confirmed consistent across the whole cluster:
    `<` is the character, `[`/`[1` is the quest-giving monster.
  - `render_quest_mockery()` (`_LHaHa`) -- an unclosed quote,
    transcribed honestly as the fragment it is (likely closed by
    `_LRidAns`'s own file-dispatched `RANS.X`, not accessible to this
    project).
  - `QUEST_BUT_THEN_TEMPLATE` (`_LBThen`) -- a bare precursor clause,
    the same shape `EXPLORE_NOT_PRESENT_PREFIX` (Phase 110) already
    established.
  - `render_monster_threat_death()` (`_LWGrr`/`_LPrDie`) -- a
    confirmed real two-`Say()` pair: `_LWGrr` opens a quote it never
    closes, and `_LPrDie` starts lowercase and ends with the missing
    closing `"` -- the same concatenation evidence pattern already
    used to confirm `SPELL_CAST_ANNOUNCEMENT` concatenates (Phase
    122).
  - `render_quest_item_taken_anyway()`/`render_quest_errand_thanks()`
    (`_LWTake`/`_LWErrand`) -- each opens a quote with no visible
    closing `"`, transcribed honestly as fragments.
  - Eight complete, self-closing quoted sentences covering the
    quest's own outcome states: `render_quest_wrong_answer()`,
    `render_quest_progress_acknowledged()`,
    `render_quest_insufficient_skill()`,
    `render_quest_insufficient_price()`,
    `render_quest_service_not_performed()`,
    `render_quest_hero_not_tasty()`, `render_quest_no_agreement()`,
    and `render_quest_reward_already_given()` (`\` is `PROSE.TXT`'s
    own Magic Item marker).
  - `render_quest_fled_in_fear()` (`_LFKOnly`) -- plain narration (no
    quotes), the character's own courage fails during the quest
    encounter.
  - Non-breaking: full suite passed unchanged (1897 passed) before any
    new tests were written -- new functions with no existing call
    sites. 19 new tests added (1916 passed total) in
    `tests/test_turn_report.py`.
- **Phase 130 (current)**: `models/monster.py MonsterEngagementState`
  (new) + `report/turn_report.py render_monster_offers_raid_truce()`
  -- the last real narrative fragment found while sweeping the
  remainder of `RUMORS.PAS` past `SAY.PAS`'s own now-fully-scanned
  1402 lines. `RUMORS.PAS`'s `Check_Raid` procedure (~lines 2279-2286)
  is dispatched inline within `FD`'s own `MTALK.X2` file-dispatch flow
  (not the main `Say_Code` `CASE`) and references `fstate[_feat1-256]
  = Bold` -- `CTBOTH.PAS`'s `state = (Dead,Hired,Mercenary,Zomboid,
  Bold,Sold,Loser,Calm)` (~line 1260), with real display names from
  `CTBOTH.PAS`'s own `statname` array (~line 1527): "Dead", "Hired",
  "Mercenary", "Skeletal", "Emboldened", "Sold Soul", "Loser",
  "Calmed". `render_monster_offers_raid_truce()` renders the one real
  sentence gated on this state (`_ = Bold` = "Emboldened"): a
  quest-giving monster offers to stop raiding a province if its own
  quest is fulfilled -- ties directly to Phase 129's Monster Quest
  Fulfillment cluster.
  - **`RUMORS.PAS` is now fully swept for narrative content.** The
    large remaining block this phase also inspected (~lines
    1000-1673: `Write_MF`, `Check_PToo`, `Write_Entry`,
    `Write_Standby`, `Check_News`/`Fin_News`, `Batch_Print`/
    `Summ_Print`/`Batch_Copy`) turned out to be the original 1990s
    play-by-mail operator's own billing/administrative infrastructure
    (subscription invoicing, standby-player recruitment forms, a
    news feed, batch-printing utilities) -- genuinely out of scope for
    game-mechanics modeling, not a gap. Everything else in the file is
    either the rendering engine itself (already reverse-engineered by
    `report/prose.py`, Phase 58) or plumbing utilities.
  - Non-breaking: full suite passed unchanged (1916 passed) before any
    new tests were written -- new module/function with no existing
    call sites. 5 new tests added (1921 passed total) in
    `tests/test_monster.py`/`tests/test_turn_report.py`.
- **Phase 131 (current)**: sweeps every remaining `.PAS` file beyond
  `SAY.PAS`/`RUMORS.PAS`/`CTBOTH.PAS` (`AKT.PAS`, `SPEAK.PAS`,
  `TRANS.PAS`, `LNAMES.PAS`, `PRNAMES.PAS`, `CTME.PAS`, `YAK.PAS`,
  `DEF2.PAS`, `REPORTS.PAS`), per the user's own "scandaglia tutti gli
  altri file .PAS" request. Most are either already-covered
  (`AKT.PAS`'s magic-item names duplicate `models/treasure.py`'s
  independently-sourced `TREASURE_NAME`, Phase 77; `CTME.PAS`'s
  `dname` array duplicates `models/discovery.py DISCOVERY_NAME`,
  Phase 91/93) or out of scope (`LNAMES.PAS`/`PRNAMES.PAS` are
  leader/province name pools for world generation, excluded per
  `models/feature.py`'s own no-world-gen precedent; `TRANS.PAS` is a
  file-conversion utility; most of `DEF2.PAS` is printer/shield-
  graphic/file-I/O plumbing). Two genuine findings resulted:
  - **`models/advanced_ability.py`**: (1) a docstring correction --
    `SAY.PAS Imp_Spab` (~lines 1338-1351), `SPEAK.PAS PW_Spab` (~lines
    33-40), and `REPORTS.PAS` (~line 643, `FD('c:\tp\prose\
    saname.x2', S_Red, 1001+spabord[ab,skil-4])`) together confirm the
    Advanced Ability pool-selection mechanic (`spabord[ability,
    level-4]`) is a real, deterministic lookup table, not a dice roll
    -- correcting Phase 128's "unsourced, possibly random" note. The
    table's actual values remain unrecoverable since its declaring
    units (`defines`, `mboth`, named in `SPEAK.PAS`'s own `uses`
    clause) have no source anywhere in `Programma Pascal.zip`, only
    compiled `.TPU` forms. (2) two new real, fully-recoverable dicts
    from `SPEAK.PAS Check_MSpab`/`Check_DSpab` (~lines 66-90):
    `UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS` (6 named-unique `Treasure`
    items -> the tuple of `Ability` values each re-checks while held,
    e.g. Crown of Rohan -> March + Tactical) and
    `DISCOVERY_ADVANCED_ABILITY_CHECKS` (the 20 `fix`/`wreck`
    `Discovery` members -> one `Ability` each, derived via Pascal's
    own `Shr 1` bit-shift arithmetic on the enum ordinal: `fix0`/
    `fix1` -> Tactical ... `wreck8`/`wreck9` -> Sage). Both cross-
    reference already-modeled `models/treasure.py Treasure` (Phase 77)
    and `models/discovery.py Discovery` (Phase 91/93) member names
    directly, with no new vocabulary invented.
  - **`report/prose.py`**: found `YAK.PAS`'s real `End_Punct`
    definition (`c='.' or c='?' or c='!'`) and confirmed, via Turbo
    Pascal's own last-unit-wins `uses`-clause resolution
    (`RUMORS.PAS`'s `uses dos,crt,defines,yak,map,mboth;` lists `yak`
    after `defines`), that this is the version `RUMORS.PAS` actually
    calls -- resolving a gap this module's docstring had flagged since
    Phase 58 ("`End_Punct` ... compiled unit with no source available"). Combined with
    `RUMORS.PAS`'s own real `Stop_Punct` definition (space, `{`, `}`,
    `,`, plus `End_Punct`), the true `/R` word-boundary stop-character
    set is exactly `{' ', '{', '}', ',', '.', '?', '!'}` -- no colon,
    no semicolon. `_STOP_CHARACTERS` previously, wrongly, also
    included `:`/`;`; corrected to the real set. Verified harmless in
    practice before committing: the full suite passed unchanged with
    the fix applied, confirming no already-tested template's `/R`
    choice ever sat next to a colon or semicolon.
  - Non-breaking: full suite passed unchanged (1923 passed, including
    the 2 new `prose.py` boundary-character tests) before the new
    `advanced_ability.py` dict tests were written. 5 new tests added
    (1928 passed total) in `tests/test_advanced_ability.py`/
    `tests/test_prose.py`.
- **Phase 132 (current)**: closes the two remaining decode-only
  actions, SEARCH (Phase 19) and TRADE (Phase 20), each to the honest
  limit its own real sourcing allows.
  - **SEARCH now actually executes.** `turn/encounter.py` (Phase 48)
    is extended with `Combatant.melee_damage_range` (default the
    character-only 1-6 die, non-breaking for every existing
    character-vs-character caller) so a monster combatant can fight
    with its own species-specific die from `models/monster.py
    MONSTER_STATS` (rulebook's own Monster Table: Giant 1-7, Gargoyle
    1-6, etc. -- not the generic character rule). New `turn/
    search_execution.py execute_search()` validates co-location and a
    real Melee duel against the feature's guardian monster (rulebook
    [3.3]/[5.0]) *when* the guardian's stats are sourced (only 6 of 61
    real species have them -- the rulebook's own table is an explicit
    "partial listing") *and* the decoded Encounter Plan actually
    contains a Melee tactic (empirically the dominant real case per
    `turn/search_decode.py`'s own docstring: "every real Search order
    ends in Melee and/or Scout"); otherwise it honestly reports
    `combat_resolved=False` with a reason rather than guessing at
    unsourced monster stats or unrequested tactics. A win sets the
    feature's own `looted` flag (`fstate[fn] = Dead`, "sacked &
    looted"); a loss kills the searching leader -- personal combat's
    generic [5.0] rule ("until one combatant is killed"), no
    Duel-style [7.1] carve-out, the same reasoning already established
    for a Challenge loser (Phase 50). Wired directly into
    `plan_dispatch.py`'s SEARCH dispatch (no opt-in flag needed, since
    there was no prior GameState-mutating behavior to preserve).
  - **TRADE stays decode-only, still by design.** `turn/trade_decode
    .py`'s own docstring already established Trade as this project's
    least-confirmed decode module: `obj`'s item-id/gold-amount
    ambiguity is unresolved, and -- the blocker that matters here --
    **no recipient field is decoded at all**, even though the
    rulebook requires "a co-located character who will receive it."
    Rather than force a fake "execution" by guessing a recipient
    position, Phase 132 adds `turn/trade_execution.py
    execute_gold_give()`: a real, fully-sourced primitive for [3.18]'s
    one unambiguous sub-rule -- "Only a King may use this 'Give Gold'
    order... no more than 10% of the size of his treasury" -- taking
    the recipient kingdom as an explicit caller-supplied parameter
    rather than one decoded from `TradeRequest`. Deliberately **not**
    wired into `plan_dispatch.py`: Search's gap was a missing
    *resolver* (now built); Trade's gap is a missing *decoded field*,
    which wiring code cannot paper over without inventing data. A
    magic-item Give isn't attempted even at this reduced scope either
    -- `models/item.py` is still an unpopulated stub, a second,
    independent structural gap on top of the missing recipient.
  - Non-breaking: full suite passed unchanged (1930 passed, including
    updated `test_plan_dispatch.py` SEARCH assertions) before the new
    Phase 132 tests were written. 19 new tests added (1949 passed
    total) in `tests/test_encounter.py`, `tests/test_search_execution
    .py` (new file), and `tests/test_trade_execution.py` (new file).
- **Phase 133 (current)**: closes Trade/Give's last real gap -- the
  recipient -- from real domain knowledge the user supplied directly
  (2026-07-13), quoted and cross-checked in full in `turn/trade_decode
  .py`'s own docstring.
  - **The item-vs-gold disambiguation and recipient field are both now
    confirmed.** `obj` is resolved by checking whether the giver
    actually possesses an item with that id (item takes priority if
    so, matching the user's own "si passa l'oggetto e non l'oro"); if
    not, `obj` is a gold amount, gated by [3.18]'s already-sourced 10%
    cap -- independently cross-validated by the user's own example
    (giving 3 gold requires >= 30 in the treasury, exactly 3 = 30 *
    10%). The recipient is `TradeRequest.target_leader_id`
    (`extra[1]`/`n1`), structurally confirmed against `HostAK/TP/
    DEF2.PAS`'s `R_HPlan`/`W_HPlan` (Trade's own `CASE` branch reads
    exactly one further value right after the standard triple) -- the
    Pascal source proves *a* second field exists there; the user's own
    description of the `GI <item_or_gold> <target>` order syntax is
    what confirms *what it means*.
  - **`turn/trade_execution.py execute_give()`** (new) resolves a real
    `TradeRequest` end-to-end: co-location (the user's own "che si
    trova nella stessa provincia"), that both giver *and* recipient are
    Kings for the gold path (rulebook: "give... to *other* Kings", not
    just "only a King may give"), and the 10% cap. The item path stays
    honestly unresolved -- `giver_possesses_item` defaults to `False`
    since this project still has no item-ownership registry to check
    real possession (`models/item.py` remains an unpopulated stub), so
    every real dispatch falls through to the gold path, the only one
    this project can actually execute. **TRADE is now wired into
    `plan_dispatch.py`** as real execution (previously blocked purely
    by the missing recipient).
  - **Real, previously-unrendered `SAY.PAS` corroboration**, found
    while verifying the user's mechanic against the Pascal source
    (~lines 517-520): `_LTrade` (item given), `_LGGive` (gold given),
    and, matching the user's own described failure almost verbatim,
    `_LNHave` ("< didn't have on hand the full # gold requested, so ")
    plus `_LNDeal` (reciprocal-trade condition not met) -- four real
    templates, all previously unrendered, now added to `report/
    turn_report.py` as `render_item_give()`/`render_gold_give()`/
    `render_insufficient_gold()`/`render_trade_deal_failed()`.
  - Non-breaking: full suite passed unchanged (1951 passed) before the
    new Phase 133 tests were written. 13 new tests added (1964 passed
    total) in `tests/test_trade_decode.py`, `tests/test_trade_execution
    .py`, `tests/test_plan_dispatch.py`, and `tests/test_turn_report.py`.
- **Phase 134 (current)**: implements `REPORTS.PAS Set_Defend`'s real
  missed-deadline auto-fill for the first time -- previously only cited
  as background in `plan_dispatch.py`/`aspy_defend_decode.py`'s own
  docstrings, never actually built. Found while sweeping `DEF2.PAS`/
  `REPORTS.PAS` for remaining unmodeled mechanics, per the user's own
  request.
  - New `turn/missed_deadline.py build_missed_deadline_plan(state,
    leader_id)` constructs the exact `ActionPlan` `Set_Defend` (~lines
    2201-2211) assigns to a King's leader who missed the move
    deadline: phase 0 is `Defend` only if the leader actually commands
    an army (`AA_Led(l2) > 0`) -- a condition this project's own prior
    citations had dropped, silently over-stating Defend as
    unconditional; an armyless leader gets `Wait` in every phase,
    phase 0 included. Every other phase is always `Wait`.
    `lobjects[0]:= lx[l2]*XMULT+ly[l2]` (the Pascal source's own
    numeric encoding of the leader's location) needs no decoding here:
    `turn/defend_execution.py`/`turn/turn_processor.py`'s own DEFEND
    handling already computes reactive coverage from the leader's live
    `HexCoord`, never from a dispatched phase's `obj` -- so the
    synthetic phase's `obj` stays an inert placeholder, dispatched
    exactly like any real, player-submitted plan via `turn/
    plan_dispatch.py run_leader_plan()`.
  - Not itself a "missed the deadline" detector -- this project has no
    move-file-submission-timestamp concept in `GameState` at all; the
    precondition is caller-supplied, the same "caller supplies what
    decode/state can't determine" pattern already used by Phase 132/133's
    `execute_gold_give()`/`execute_search()`.
  - Non-breaking: full suite passed unchanged (1964 passed) before the
    new Phase 134 tests were written. 3 new tests added (1967 passed
    total) in `tests/test_missed_deadline.py` (new file).
- **Phase 135**: researched `REPORTS.PAS Rep_Econ`'s Discovery
  effect-magnitude formulas (`fix`/`wreck` ability-skill bonus,
  `bild` anti-spell targets, `crunch` revenue-bonus percentages) --
  found, on inspection, that **all three were already fully modeled**
  in Phase 93's own `models/discovery.py` (`DISCOVERY_ABILITY_BONUS`/
  `DISCOVERY_ANTISPELL_TARGET`/`DISCOVERY_REVENUE_BONUS_PERCENT`,
  sourced from the identical `Rep_Econ` `CASE` block, already quoted
  verbatim in that module's own docstring). No new code needed --
  recorded here so a future sweep doesn't re-flag it.
- **Phase 136 (current)**: `turn/intelligence_estimate.py` (new) --
  `REPORTS.PAS Align_Est`/`Temper_Est` (~lines 43-58), a real,
  previously unmodeled imperfect-information mechanic found in the
  same DEF2.PAS/REPORTS.PAS sweep, per the user's own request.
  - `estimate_alignment()`/`estimate_temper()` implement the exact
    ±1-ordinal noise formula: a perfect-detection agent (Psychic Mage
    office-holder, or -- alignment only -- the `Detect_Align`
    advanced ability, almost certainly this project's own
    `AdvancedAbility.KNOW_ALIGNMENT_TALENT` by semantic match) sees
    the true value; anyone else gets the true value nudged by exactly
    one enum ordinal based on id parity, clamped to the enum's own
    real range (`Alignment.SPECIAL`/`Temper.BERSERK` are each enum's
    own highest ordinal, confirming the clamp bounds directly) --
    deterministic from both ids' parity, not RNG-driven, exactly what
    the Pascal source computes.
  - **Temper's second parity term is the agent's own birth
    x-coordinate** (`bornx[agent] and 1`), not the agent's id --
    a real, distinct difference from `Align_Est`'s own formula, not
    an oversight. This project has no `LeaderState` field for a
    leader's birth coordinate (character-creation/world-generation
    data, the same category of gap already declared unbuilt
    elsewhere), so `estimate_temper()` takes it as an explicit
    caller-supplied parameter.
  - `perfect` is caller-supplied for both functions: neither
    office-holding (Phase 137's own subject) nor per-leader advanced-
    ability possession is tracked anywhere in `GameState` yet.
  - Deliberately not modeled: the `ln < 256` character-vs-monster
    branch (a monster's own implied alignment has no available
    formula, `Agent_Align`'s own source is missing, same lost-unit
    gap as `spabord`), and the `2880+`/`2896+` prose-dispatch-code
    offsets (the target `.X2` prose file isn't in the available
    archive) -- this module exposes the real estimated enum member
    directly instead.
  - Non-breaking: full suite passed unchanged (1967 passed) before
    the new Phase 136 tests were written. 10 new tests added (1977
    passed total) in `tests/test_intelligence_estimate.py` (new file).
- **Phase 137 (current)**: researched `REPORTS.PAS Ofc_Pts`/`Rank`
  (~lines 1128-1250) -- the real per-turn scoring formula deciding
  who holds each office (Emperor, Chancellor, Treasurer, Priest, Mage,
  and a dozen more), the last thread from the user's own DEF2.PAS/
  REPORTS.PAS sweep. **Confirmed a permanent dead end, not merely
  unattempted**: nearly every office's own formula reads at least one
  of ten distinct per-leader statistics (`lgenp`/`ladmp`/`lmhpp`/
  `lwmsp`/`oops`/`tipts`/`seatax`/`alltax`/`lfdisc`/`ldiscp`) that an
  exhaustive grep of all 14 available `.PAS` files confirms are
  declared nowhere in the archive -- the same missing compiled-only
  `mboth`/`defines` units already responsible for `spabord`'s lost
  data (Phase 131) and `Agent_Align`'s missing source (Phase 136), but
  affecting eight-plus statistics simultaneously here instead of one.
  A couple of individual formula terms are independently derivable
  (`M_Skill` from `LeaderState.skills`; `Treasurer`'s own points are
  plausibly just a King's `KingdomState.treasury`), but implementing
  only the 1-2 offices that happen to dodge the missing arrays, while
  the other 13+ stay permanently unimplementable, would misrepresent
  partial coverage as a real system. Documented in `models/office.py`'s
  own docstring so a future sweep doesn't re-open this dead end;
  no code changes beyond that docstring addendum, no new tests needed.
  This closes out the full DEF2.PAS/REPORTS.PAS sweep the user
  requested (Phases 134-137).
- **Phase 138 (current)**: wires `turn/missed_deadline.py` (Phase 134)
  into `turn_processor.py`, per the user's own request to connect the
  "orphan" modules left standalone after the DEF2.PAS/REPORTS.PAS
  sweep. New `build_missed_deadline_turn_leaders(state, kingdom_id)`
  builds a `TurnLeader` for every leader belonging to `kingdom_id`
  using `build_missed_deadline_plan()`, so a caller who already knows
  a kingdom submitted no move file this turn can merge that kingdom's
  own Defend/Wait auto-fill leaders straight into the `turn_leaders`
  list passed to `run_turn()`, dispatched exactly like any real,
  parsed plan. `kingdom_id` stays caller-supplied -- `run_turn()`
  itself still has no "did this kingdom submit a move file" detection
  built in, since `GameState` tracks no such timestamp anywhere.
  - `turn/intelligence_estimate.py` (Phase 136) stays unwired for now:
    re-checking exactly where `REPORTS.PAS Align_Est`/`Temper_Est`
    are actually called from turned up **zero call sites anywhere in
    the available Pascal archive** -- they're declared and defined,
    but never invoked from any accessible source. Wiring them into a
    real consumer (e.g. extending `turn/aspy_execution.py`'s
    `SpyReport` with a "characters spotted, with estimated
    alignment/temper" section) would therefore be this project's own
    design choice, not a sourced integration point -- flagged for the
    user rather than invented unprompted.
  - Non-breaking: full suite passed unchanged (1977 passed) before the
    new Phase 138 tests were written. 4 new tests added (1981 passed
    total) in `tests/test_turn_processor.py`.
- **Phase 139 (current)**: wires `turn/intelligence_estimate.py`
  (Phase 136) into `turn/aspy_execution.py`'s `SpyReport`, per the
  user's own explicit go-ahead to build a consumer despite Phase 138's
  finding that `Align_Est`/`Temper_Est` have **zero call sites anywhere
  in the available Pascal archive**. This is documented here as this
  project's own design choice (ASpy is the one action whose entire
  rulebook purpose, [3.14], is "report on what's here," making a
  spotted-characters list a natural fit for the estimation formulas'
  shape), not presented as a sourced integration point.
  - `models/game_state.py LeaderState` gains two new optional fields,
    `temper: Temper | None = None` and `birth_x: int | None = None`,
    following the exact same "`None` = no data recorded" convention
    `skills: SkillTable | None = None` already established (Phase 30).
    Neither has a populating consumer yet -- the same category of gap
    `skills` itself was in before Phase 31's `kingdom_bridge.py`.
  - `SpyReport` gains `spotted_characters: list[SpottedCharacter]`
    (new dataclass: `leader_id`, `name`, `estimated_alignment`,
    `estimated_temper`), derived from `GameState.leaders_at()` at the
    caster's own province, excluding the caster itself.
  - A spotted leader's true alignment is read from their own
    `KingdomState.alignment` (the same per-kingdom field
    `turn/challenge_execution.py`'s Neutral-duelist-bonus check already
    treats as characterizing a leader in that kingdom's service);
    `None` for an independent Hero with no kingdom. True temper is read
    from the new `LeaderState.temper` field; `None` if unrecorded.
  - `execute_aspy()` gains two new caller-supplied keyword flags
    matching the real formula's own asymmetry (documented in Phase
    136): `caster_holds_psychic_mage_office` grants perfect detection
    for **both** alignment and temper; `caster_has_detect_align` only
    ever helps alignment -- the real `Temper_Est` source has no
    advanced-ability bypass at all.
  - Non-breaking: full suite passed unchanged (1981 passed) before the
    new Phase 139 tests were written. 8 new tests added (1989 passed
    total) in `tests/test_aspy_execution.py`.
- **Phase 140 (current)**: `models/item.py ItemInstance` (rewritten
  from the Phase 1 `MagicItem` stub) plus a real `GameState.items`
  ownership registry, closing Trade/Give's own "no item-ownership
  registry exists" gap (Phase 133) and `turn/use_mi_decode.py`'s
  parallel "can't resolve an item-instance id" gap (Phase 24) at the
  same time -- both were blocked on the exact same missing structure.
  - Sourced from `RUMORS.PAS`'s `Add_Tr` procedure (~line 646) and the
    `treaslist`/`trowner`/`trcharges` triple it populates: every
    physical magic item in play is one slot across those three
    parallel arrays (type, owning leader or `noleader`, charges
    remaining). Confirmed, not guessed: `DEF2.PAS`'s `R_HPlan`/
    `W_HPlan` index straight into `treaslist[lobjects[m]]` to resolve a
    Use_MI phase's item, and `REPORTS.PAS`'s own per-leader inventory
    listing (`FOR tn:= 0 TO ntreasures-1 DO IF trowner[tn] = tro`, ~line
    540) prints `"<ItemName> (#<tn>): ..."` in a character's own turn
    report -- the same instance id a Give order's item field refers to.
  - `GameState.add_item(treasure, owner_leader_id, charges=0)` mirrors
    `Add_Tr` directly (including masking `charges` to a byte, matching
    the Pascal source's own `tch and 255`); `items_held_by(leader_id)`
    mirrors the `trowner[tn] = tro` inventory loop; `transfer_item()`
    mirrors a direct `trowner[tn]:= ...` assignment. Ids are allocated
    monotonically (`new_item_id()`, mirroring `new_army_id()`) rather
    than replicating `Add_Tr`'s own free-slot-reuse scan against the
    still-missing `maxfeatures` constant -- the same simplification
    already made for army/leader ids.
  - **Deliberately scoped to leader-held items only**: the real Pascal
    arrays also cover monster/feature-guarded treasure (slots
    `0..maxfeatures`, owner-encoded via a `feature_id + 256`
    convention, e.g. `REPORTS.PAS`'s `trowner[fn] <> fn+256`). That
    range needs the still-missing `maxfeatures` constant and this
    project's still-nonexistent monster/feature loot pipeline, neither
    of which this phase attempts -- `ItemInstance.owner_leader_id` is
    only ever a leader id or `None`, never a feature encoding.
  - `turn/trade_execution.py execute_give()` now checks
    `state.items.get(request.obj)` for real: if the giver genuinely
    owns that instance, it's transferred via `transfer_item()` with no
    King/kingdom requirement on either side (the user's own domain
    knowledge: "Se l'eroe appartiene a un altro reame, l'oggetto passa
    di mano"), replacing the previous `giver_possesses_item` caller
    flag entirely -- there is no longer any case where the item path
    silently can't be evaluated.
  - **Still not attempted**: an automatic world-gen/loot trigger that
    calls `add_item()` (no Pascal source describes how instances first
    come into existence, beyond the single narrow Valhalla-visitor
    `Add_Tr` call site already documented in Phase 24's own module), and
    a real `execute_use_mi()` resolver that consumes the now-resolvable
    `item_instance_id` (Use_MI still only decodes, per Phase 24 -- this
    phase makes the id resolvable, not executed).
  - Non-breaking: full suite passed unchanged (1991 passed, reflecting
    the `execute_give()` test rewrite from a caller-flag scenario to a
    real ownership one) before the new Phase 140 tests were written. 8
    new tests added (1999 passed total) in `tests/test_game_state.py`.
- **Phase 141 (current)**: `turn/use_mi_execution.py` (new) --
  `execute_use_mi()`, the real consumer Phase 140's item-ownership
  registry unblocked (per that phase's own "still not attempted" note).
  Resolves `UseMIRequest.item_instance_id` against `GameState.items`,
  requires the acting leader to actually own it, and dispatches by
  `TreasureCategory`:
  - **The 20 spell-casting wands** dispatch into `turn/
    cast_execution.py execute_cast()` for the mapped `Spell`
    (`TREASURE_WAND_SPELL`), via a new `wand_skill_level` parameter
    threaded through `execute_cast()` and all 13 of its `_execute_*`
    spell helpers. Two real, sourced mechanical differences from an
    ordinary Cast: rulebook [3.11] ("A spell cast from a magic item is
    automatically successful" -- no roll at all), and `TREASAB.X2`'s
    own label for every one of the 20 wands reading `"Cast '<Spell>' at
    skill-2"` (Phase 77's own transcription) -- every level-dependent
    magnitude (Tornado's/Plague's destroy chance, Illus_Armies'
    strength bonus, Bless's graveyard-cleanup chance, Skeletal_Army's
    raised-army count) uses a fixed skill level of 2 regardless of the
    caster's own recorded `LeaderState.skills`. A wand isn't consumed
    by a single cast -- `ItemInstance.charges` is read but not
    decremented, since no Pascal source for the actual per-cast charge
    spend is in the available archive either; an honest gap, not a
    silent zero-cost assumption.
  - **The 15 one-shot skill books** apply a direct, self-consuming +1
    to the mapped `Ability` (`TREASURE_BOOK_ABILITY`) on the reader's
    own `LeaderState.skills` (creating a fresh all-zero `SkillTable`
    first if none was recorded, the same convention `turn/
    practice_execution.py` already established), clamped to
    `skillrange`'s own real ceiling of 9 (`CTBOTH.PAS`), then the item
    is removed from `GameState.items` entirely via the new
    `GameState.remove_item()` -- "self-consuming" read literally.
  - **Every other category** (passive ability items, combat/leadership
    weapons, anti-magic amulets, monster-command items, gold hoards,
    quest items, the sentinel, named uniques, unused extension slots)
    fails with a clear "operates automatically" reason -- never a
    legitimate Use_MI target per [5.9].
  - Wired into `turn/plan_dispatch.py` (`_dispatch_use_mi`), replacing
    the previous bare `decode_use_mi_phase()` return. Zero real Use_MI
    phases exist in any of the 10 sample files, so this stays
    unvalidated against real data -- same situation Fire and Trade were
    in before their own executors landed.
  - Non-breaking: full suite passed unchanged (1999 passed, after
    updating `test_plan_dispatch.py`'s own stale "decode-only" USE_MI
    assertion to match the new real-execution return type) before the
    new Phase 141 tests were written. 10 new tests added (2009 passed
    total): 9 in `tests/test_use_mi_execution.py` (new file) plus 1
    more real-dispatch test in `tests/test_plan_dispatch.py`.
- **Phase 142 (current)**: `report/turn_report.py describe_give()`
  (new) -- the first slice of the "turn report assembler" thread
  flagged since Phase 61's own scope note ("a turn-events log, a
  separate, much larger follow-up"). Rather than a global events log,
  this follows the exact composition pattern `describe_battle()`
  (Phase 61) already established: a `describe_*` function that
  consumes an already-computed `*ExecutionResult` dataclass and calls
  the relevant `render_*` functions in the real dispatch order, with
  caller-supplied display names (no name-synthesis system exists in
  this project).
  - Consumes `turn/trade_execution.py TradeExecutionResult` (Phase
    133/140): a successful item transfer renders `_LTrade`
    (`render_item_give`), a successful gold transfer renders `_LGGive`
    (`render_gold_give`), and a failure specifically from [3.18]'s 10%
    treasury-cap check renders `_LNHave` (`render_insufficient_gold`).
    Every other failure reason (giver/recipient not found, not
    co-located, recipient not a King, no recipient decoded) has no
    sourced narrative template and renders nothing.
  - **Corrects a now-stale docstring**: `render_item_give`'s own
    comment used to say the item path was "still unmodeled at the
    `GameState` level (no item-ownership registry)" -- true when
    written (Phase 133), false since Phase 140's real registry.
  - `render_trade_deal_failed` (`_LNDeal`) is deliberately **not**
    called by `describe_give()`: it renders a reciprocal two-way
    trade's failed condition, but `turn/trade_decode.py` never decodes
    a recipient-side reciprocal item id at all, so `execute_give()` has
    no state that could ever produce this outcome -- documented as a
    genuinely sourced but currently-unwired renderer, not deleted.
  - The other 100 of this project's 104 `render_*` functions still
    have no `describe_*` composer -- explicitly left for future phases
    of the same shape, one action/mechanic at a time, rather than
    attempted all at once.
  - Non-breaking: full suite passed unchanged (2009 passed) before the
    new Phase 142 tests were written. 6 new tests added (2015 passed
    total) in `tests/test_turn_report.py`.
- **Phase 143 (current)**: `report/turn_report.py describe_hire()`/
  `describe_fire()` (new) -- the second slice of the report-assembler
  thread, plus a genuine correctness fix found while building it.
  - **`turn/plan_dispatch.py _dispatch_fire()` previously returned a
    bare `FireRequest`, always** -- the caller had no way to tell
    whether the Fire actually happened at all, unlike every other
    dispatcher in this project (Hire's own `HireExecutionResult`
    included). Phase 143 adds a real `FireExecutionResult` (`fired`/
    `reason`), matching the `hired`/`reason` shape `HireExecutionResult`
    already established, so `describe_fire()` has a real signal to
    build a sentence from.
  - `describe_hire()` consumes `HireExecutionResult` (Phase 17):
    `render_hire_accepted` (`ACCHIRE.X`) on success. **Confirmed only
    one of the three real Hire renderers is ever reachable at all**:
    `_dispatch_hire()`'s own docstring already documents that this
    project always charges the full offer and always accepts a Hire
    that's co-located and affordable ("the rulebook's Hero 'pay
    required'... isn't modeled"), so neither `render_hire_refused`
    (`REFHIRE.X`, alignment-based) nor `render_hire_counter_offer`
    (`_LCounter`, price-based) has any real trigger in
    `HireExecutionResult.reason` -- every one of its real failure
    strings ("hero not found", "cannot hire a King", "hero already in
    service", "not co-located", "insufficient treasury") is an
    administrative failure with no sourced narrative template.
  - `describe_fire()` consumes the new `FireExecutionResult`:
    `render_fire_hireling` (`FIREMAN.X`) on success; both real failure
    reasons ("hero not found", "not co-located") have no sourced
    template either.
  - Non-breaking: full suite passed unchanged (2015 passed, after
    updating `test_plan_dispatch.py`'s 4 existing Fire tests for the
    new `FireExecutionResult` return type) before the new Phase 143
    tests were written. 4 new tests added (2019 passed total) in
    `tests/test_turn_report.py`.
- **Phase 144**: `report/turn_report.py describe_practice()`
  (new) -- third slice of the report-assembler thread, consuming
  `turn/practice_execution.py PracticeExecutionResult` (Phase 44/46).
  Only two of this project's Practice renderers are ever reachable,
  and both need caller-supplied context `PracticeExecutionResult`
  alone doesn't carry, the same convention `describe_battle()`'s own
  `army_names` and `describe_give()`'s own `item_name` already
  established:
  - `render_practice_already_maxed` (`_LAlrMax`) fires when
    `result.new_skill == MAX_SKILL_LEVEL` (9, `CTBOTH.PAS`'s own
    `skillrange` ceiling) coexists with `skill_rose is False` --
    confirmed the *only* way that combination can occur:
    `attempt_skill_rise()`'s own early-return short-circuits to
    `new_skill` unchanged whenever the attempt started at 9 already; a
    failed roll from any lower level leaves `new_skill` at that lower
    level, never at 9.
  - `render_practice_tutored` (`_LTeach`) fires when the skill
    genuinely rose (`result.skill_rose`) *and* the caller supplies a
    `teacher_name` -- rulebook [3.13]'s own group-practice rule (a
    higher-skilled co-practicer), which `PracticeExecutionResult` has
    no field for at all (it doesn't even record solo vs. group). A
    solo rise with no `teacher_name` renders nothing: no sourced
    narrative template exists for solo Practice success at all.
  - Every other case (a normal failed roll, an aptitude-only rise,
    `not_implemented_for_ability`) renders nothing.
  - Non-breaking: full suite passed unchanged (2019 passed) before the
    new Phase 144 tests were written. 6 new tests added (2025 passed
    total) in `tests/test_turn_report.py`.
- **Phase 145**: `report/turn_report.py render_cast_announcement()`
  + `describe_cast()` (both new) -- fourth slice of the report-assembler
  thread, and the first to consume `turn/cast_execution.py
  CastExecutionResult` (Phase 29/59/60/141). Unlike the other
  `describe_*` composers, Cast's own real narrative material
  (`SPELL_CAST_ANNOUNCEMENT`, Phase 122) was already sourced but never
  actually rendered by anything -- that phase's own docstring left it as
  "raw templates only; the caller composes," so this phase is the first
  real caller.
  - `render_cast_announcement()` stitches `SAY.PAS _LCast1`'s own
    opening clause (`CAST_SPELL_OPENING_COMPLETE_TEMPLATE` for
    Tornado/Bless/Plague, `CAST_SPELL_OPENING_CONTINUED_TEMPLATE`
    otherwise, keyed by `CAST_SPELL_OPENING_COMPLETE_SPELLS`) with the
    matching `SPELL_CAST_ANNOUNCEMENT[spell]` continuation clause, then
    renders the combined template through `report/prose.py render()`.
    Covers all 25 `SPELL_CAST_ANNOUNCEMENT` entries generically (any
    spell whose own entry needs a `target_name`/`province_name`/
    `terrain_name`/`army_names` raises `ValueError` naming the spell if
    it's missing), though `describe_cast()` only ever reaches one of the
    13 spells `turn/cast_execution.py` can actually apply.
  - **Two genuine, honestly-transcribed oddities surfaced by actually
    stitching the two template halves together for the first time**,
    neither silently "fixed": `Spell.ORATORY`'s own `SPNOTE.X2` entry
    already reads as a complete sentence ("< cast a spell giving magical
    powers of oratory to [.") yet `_LCast1`'s own `CASE` doesn't
    special-case it as "complete" the way Tornado/Bless/Plague are, so
    the real Pascal output redundantly says "cast a spell" twice in a
    row. `Spell.CHARM`'s own entry (".< befriended/Rcharmed [...")
    starts with a bare `.`, which lands mid-sentence right after the
    opening clause's own trailing space, producing a real, jarring
    ".< befriended..." mid-sentence full stop. Both transcribed as-is,
    the same stance already taken for `CONTROL_UNDEAD`'s mid-word
    truncation (Phase 122) and the Mermen "air-transport" wording (Phase
    127).
  - `describe_cast()` returns `None` when `result.applied` is `False`
    (a fizzled roll, an invalid target, or one of the 12 unexecuted
    spells) -- there is no real `SAY.PAS` narrative for a Cast order
    that never took effect, mirroring `describe_practice()`'s own
    "no narratable outcome" stance.
  - Non-breaking: full suite passed unchanged (2025 passed) before the
    new Phase 145 tests were written. 16 new tests added (2041 passed
    total) in `tests/test_turn_report.py`.
- **Phase 146**: `report/turn_report.py describe_use_mi()`
  (new) -- fifth slice of the report-assembler thread, consuming
  `turn/use_mi_execution.py UseMIExecutionResult` (Phase 141).
  - Wand use (`result.cast_result is not None`) delegates straight to
    `describe_cast()` (Phase 145): per rulebook [3.11] and `turn/
    use_mi_execution.py`'s own docstring, casting from a wand is a real
    Cast under the hood, so it gets the exact same
    `SPELL_CAST_ANNOUNCEMENT` narrative a top-level Cast order would --
    `wand_skill_level`'s own override (Phase 141) only changes the
    mechanics, not which sentence renders.
  - Skill-book use (`result.ability_boosted is not None`) always
    renders `None` -- researched and confirmed absent from the
    available archive, not merely unfound: `TREASAB.X2`'s own book
    labels (`models/treasure.py TREASURE_LABEL`, e.g. "+1 Melee when
    read") are terse inventory text, not a turn narrative;
    `TREASURE.X2`'s per-book flavor text is dispatched by `SAY.PAS
    Desc_Treas`/`_TrDesc` only from `REPORTS.PAS List_Treas`'s own
    per-leader inventory listing (a waiting/new king browsing their
    kingdom), never from a Use_MI action; and `_TrDust` (`RUMORS.PAS`
    story code 5001, "it crumbled to dust...", the one candidate that
    would fit a book's last-charge moment) has no real emission site
    anywhere in the archive -- an orphaned constant, not a live
    narrative path.
  - Every other case (`result.applied is False`: item not found, not
    owned, or not a Use_MI target) also renders nothing.
  - Non-breaking: full suite passed unchanged (2041 passed) before the
    new Phase 146 tests were written. 4 new tests added (2045 passed
    total) in `tests/test_turn_report.py`.
- **Phase 147**: `report/turn_report.py describe_pursue()` +
  `describe_trail()` (both new) -- sixth and seventh slices of the
  report-assembler thread, consuming `turn/pursue_execution.py
  PursueExecutionResult` (Phase 51/53) and `turn/trail_execution.py
  TrailExecutionResult` (Phase 52).
  - Both share `render_caught_up()` (`_LCatch`, Phase 120), which its
    own docstring already confirmed as "the Pursue/Trail catch-up
    moment" -- a single real, hardcoded `SAY.PAS` template covering
    both actions.
  - `describe_pursue()` renders it whenever `result.caught_up` is
    `True`, covering all three real catch-up shapes this project
    resolves (an army-vs-army battle via `result.battle_report`, an
    armyless personal duel via `result.combat_occurred`/
    `winner_leader_id`, or no combat intent at all): the catch-up
    moment is its own narrative event, independent of whatever combat
    follows. A caller with a real `battle_report` composes further with
    `describe_battle()` separately -- this function deliberately doesn't
    reach into that unrelated subsystem's own army-naming requirements,
    the same caller-composes-the-sequence stance already established
    for the Ice-Suspend cluster (Phase 123).
  - `describe_trail()` renders the same sentence whenever
    `result.spied_on` is `True`.
  - Both return `None` on failure (a failed catch-up roll, an
    army-leading mismatch for Pursue, Trail's own no-army restriction,
    or the leader/target not found) -- no catch-up happened, nothing to
    narrate.
  - Non-breaking: full suite passed unchanged (2045 passed) before the
    new Phase 147 tests were written. 6 new tests added (2051 passed
    total) in `tests/test_turn_report.py`.
- **Phase 148**: `report/turn_report.py render_skill_book_read()`
  (new), unblocking `describe_use_mi()`'s own skill-book branch, left
  rendering `None` since Phase 146.
  - **Project-original, not sourced from `SAY.PAS`/`RUMORS.PAS`**:
    Phase 146's own research (see that entry above) confirmed no real
    template exists anywhere in the available archive for the
    skill-book-read moment. Per the user's own explicit request and
    exact wording after that research came back empty ("legge il libro
    e la sua abilità aumenta di un livello"), this phase adds one --
    `SKILL_BOOK_READ_TEMPLATE = "< read the \\ and > ^ increased by one
    level!"`, using the same `\\` (Magic Item)/`^` (Ability name)
    markers `render_item_give()`/`render_practice_tutored()` already
    use. Documented in both the template's own comment and
    `describe_use_mi()`'s docstring as the one line in this module that
    isn't a transcription of anything in `HostAK/TP/PROSE/` -- the same
    "explicitly documented as an unsourced design choice" convention
    this project's own standing instructions require whenever a gap is
    filled without a source.
  - `describe_use_mi()`'s skill-book branch now renders it, but only
    when the caller supplies both new `book_name`/`ability_name`
    keyword arguments -- without either, it still renders nothing (the
    same "caller supplies what state can't determine" convention every
    composer here already follows).
  - Non-breaking: full suite passed unchanged (2051 passed) before the
    new Phase 148 tests were written. 2 new tests added (one existing
    Phase 146 test renamed for clarity, not counted as new) (2053
    passed total) in `tests/test_turn_report.py`.
- **Phase 149**: `models/army_naming.py` (new) -- closes the
  exact gap `report/turn_report.py`'s own module docstring names ("Army
  name"... "LNAMES.PAS/PRNAMES.PAS territory, a separate, entirely
  unbuilt subsystem"). That citation turned out to misidentify the
  source: `LNAMES.PAS`/`PRNAMES.PAS` are flat, one-name-per-line
  word-pool text files (leader names and province/geographic names
  respectively -- confirmed by `HostAK/MS/AKMAN.TXT` lines 525-526),
  consumed only by `AKGEN.EXE`, a separate offline world-generator whose
  own source isn't present in the archive. Army naming has nothing to
  do with either file.
  - The real mechanism lives in `HostAK/TP/YAK.PAS` lines 49-85, fully
    present in source (not compiled-unit territory): `Make_Des`
    (ordinal suffix on an integer) and `Make_AName` (ordinal + optional
    race tag + army type designation). `ordinal_suffix()` transcribes
    `Make_Des`'s `{$ELSE}` (non-Moderator, i.e. real host-engine) body
    -- this project already established `{$IFDEF Moderator}` marks the
    game-master/world-generation-side build, never the player-facing
    host this project reconstructs (`models/feature.py
    MONSTER_GUARDED_FEATURE_TYPES`, Phase 79). That body has a real,
    confirmed quirk of its own: **no 11/12/13 exception at all**, so
    army 11 is genuinely "11st" in the real host engine, not "11th" --
    transcribed as-is, not silently fixed.
  - `an` (the army id `Make_Des`/`Make_AName` ordinal-suffix) is the
    army's own array-slot index, confirmed by the routine indexing
    straight off it with no kingdom/race scoping visible anywhere --
    lines up exactly with `GameState.new_army_id()`'s own monotonic,
    game-wide counter (Phase 15); `ArmyState.army_id` is the direct
    equivalent, no translation needed.
  - Only `caller=1` is ever actually invoked (`REPORTS.PAS` lines 1652,
    1716, the only two call sites in the archive), matching
    `PROSE.TXT`'s own documented examples exactly ("the 231st Bowmen",
    "241st Axemen, 34th Legion and 145th Fleet" -- no full race
    adjective anywhere). `make_army_name()` only builds that one real,
    reachable shape.
  - `RACE_SHORT_TAG` -- a genuine source oddity, transcribed as-is:
    `CTBOTH.PAS` line 588's own `rab3` array literal has one fewer
    non-Rohan blank entry than `rname`/`radj`/`rpname`'s own confirmed-
    correct positional alignment (Phase 87), verified by parsing the
    literal's exact raw bytes. `'Roh'` -- unmistakably meant as
    Rohan's own short tag, given `'Elf'`/`'Dwf'`/`'Orc'` sit correctly
    at their own indices 1/2/3 -- lands one slot late, on the unused
    `er3` extension race (ordinal 15) instead of `Race.ROHAN` (ordinal
    14). `Race` has no `er3` member to receive it, so under strict
    positional transcription `RACE_SHORT_TAG[Race.ROHAN]` is empty --
    matching the source exactly, not what was evidently intended.
  - `Noid_Race(r)` -- a reconstruction assumption, not a directly-quoted
    source: used (`YAK.PAS` line 81, `SAY.PAS` line 744) but never
    defined anywhere in the available archive, the same compiled-unit
    status `End_Punct` had before Phase 131's discovery. Read literally
    ("no-[race-]id") and consistent with every real example never
    showing a race tag on a presumably-Human army, this project takes
    it to mean `r <> Human`.
  - Non-breaking: full suite passed unchanged (2053 passed) before the
    new Phase 149 tests were written. 11 new tests added (2064 passed
    total) in `tests/test_army_naming.py`.
- **Phase 150**: `models/game_state.py ProvinceState.name`
  (new field) + `turn/rename_province.py rename_home_province()` (new
  module) -- the province-naming half of the same gap Phase 149 closed
  for armies.
  - **Confirmed the real host engine never generates a province name at
    runtime at all**: names are baked into the world-generated map by
    `AKGEN.EXE` (source not present in the archive) and read once into
    the global `pname^[x,y]` array, which `ProvinceState.name` models
    directly. No formula exists to derive one from a `HexCoord` -- so,
    unlike army names, this stays `None` by default with no synthesis
    path at all, matching every other unmodeled-naming convention this
    project already uses.
  - **The one real, sourced runtime exception**: `DEF2.PAS
    Read_T1Names` (~lines 706-737, `{$ELSE}` non-Moderator body, the
    same real-host-engine branch already established Phase 79/149) --
    on turn 1 a player may rename their own home/capital province
    (`pname^[bornx[playkg],borny[playkg]]:= tmp`) and up to 2 starting
    leaders. `rename_home_province(state, kingdom_id, new_name)`
    implements exactly the province-rename half, using
    `KingdomState.home_province` as the real equivalent of
    `bornx[playkg],borny[playkg]`. The leader-rename half needs no new
    code -- `LeaderState.name` is already a free-form string field a
    caller can set directly.
  - **Confirmed out of scope, not guessed at**: `Read_T1Names` reads
    from `miscfile`, a separate input stream from the `AK3__T*.K1` move
    files `parser/k1_moves.py` already handles -- no sample of
    `miscfile`'s own format exists anywhere in this project's data, and
    the archive documents it no further. This phase only implements the
    mechanism itself (apply an already-known name); wiring a real
    trigger from a submitted file is blocked on real `miscfile`-format
    sample data this project doesn't have.
  - Non-breaking: full suite passed unchanged (2064 passed) before the
    new Phase 150 tests were written. 5 new tests added (2069 passed
    total) in `tests/test_rename_province.py`.
- **Phase 151**: `report/turn_report.py describe_turn_results()`
  (new) -- the missing link between the nine `describe_*()` composers
  built across Phases 142-148 and real turn data. Before this phase,
  every `describe_*()` call site anywhere in the project was test-only,
  using hardcoded literal strings for character/hireling/target names --
  none was ever invoked from `turn/turn_processor.py run_turn()`'s own
  output.
  - Iterates `list[PhaseDispatchResult]` (`turn/plan_dispatch.py`'s own
    flat per-phase result list, `run_turn()`'s direct output), resolving
    `leader_id` to a display name via `GameState.leaders` -- always
    available, no gap -- and skipping any entry that already carries an
    `error`.
  - **Auto-wired**: HIRE and FIRE (`HireExecutionResult.request.hero_id`/
    `FireExecutionResult.request.hero_id` resolve the hireling directly);
    CAST and USE_MI's wand-cast path, but only for the subset of spells
    already known (Phase 145's `_CAST_ANNOUNCEMENT_TARGET_SPELLS`) to
    target a character id rather than a province --
    `_AUTO_RESOLVABLE_CAST_TARGET_SPELLS = {KILL_ENEMY, RESURRECTION,
    ILLUS_ARMIES, ORATORY, CHARM}`. Any other spell (e.g. EARTHQUAKE,
    which needs a `province_name` this function has no way to resolve --
    Phase 150's own confirmed province-naming gap) is skipped outright,
    never passed to `describe_cast()` with a missing name.
  - **Caller-supplied only**: PRACTICE requires an explicit
    `ability_names: dict[Ability, str]` map parameter -- no
    `Ability`-to-display-name table exists anywhere in this project yet
    (the real `CTBOTH.PAS anoun`/`adesc` `abstrs` arrays at lines
    143-149 were never verified against `RUMORS.PAS Say_Options` to
    confirm which one is the real PROSE.TXT `^` marker, so this phase
    doesn't invent an unverified table -- the same "don't guess" line
    already held in Phases 142-150). Without the map, PRACTICE entries
    are skipped.
  - **Confirmed structurally unwireable, not merely deferred**: PURSUE,
    TRAIL, and TRADE. Direct inspection of
    `PursueExecutionResult`/`TrailExecutionResult`/`TradeExecutionResult`
    shows none retains any target/recipient id at all, and
    `PhaseDispatchResult` itself only keeps `action`/`result`/`error`
    (the original decoded `PlanPhase`/request is discarded before this
    function ever sees it) -- these three actions cannot be auto-wired
    without a separate, larger change to `PhaseDispatchResult` or those
    result types. Explicitly out of scope for this phase.
  - `describe_battle()` stays out of this dispatch entirely, unchanged
    from Phase 61 -- it needs a `BattleReport` and multi-army name maps
    `PhaseDispatchResult` doesn't carry on its own.
  - Non-breaking: full suite passed unchanged (2069 passed) before the
    new Phase 151 tests were written. 12 new tests added (2081 passed
    total) in `tests/test_describe_turn_results.py`.
- **Phase 152**: `models/province_names.py` (new) +
  `turn/rename_province.py assign_province_name()` -- closes the
  non-capital half of the province-naming gap Phase 150 left open.
  - **Project-original, not a Pascal transcription, and explicitly
    user-authorized**: Phase 150's own research confirmed the real host
    engine never generates a province name at runtime at all -- names
    were baked into the world-generated map by `AKGEN.EXE`, an offline
    tool whose own source isn't in the archive, so there is no
    algorithm anywhere to transcribe for the ~99% of provinces that
    aren't a kingdom's own capital. The user supplied a real name list
    directly (`Desktop/Nomi province.txt`), organized by terrain --
    30 Desert, 50 Forest, 40 Jungle, 80 Sea, 50 Mountain, 50 Plains
    names -- and asked for it to fill the gap, the same "user authors
    replacement content for a confirmed-unsourced gap, explicitly
    labeled as project-original" pattern already established for
    Use_MI's skill-book-read narrative (Phase 148). Every name is
    transcribed verbatim in the order supplied, including two
    incidental repeats in the Sea pool ("Frog Sea", "Pocket Sea" each
    appear twice) -- not deduplicated, since it's the user's own data.
  - `PROVINCE_NAME_POOLS: dict[Terrain, tuple[str, ...]]` covers every
    real `Terrain` member except `NO_TERRAIN` (nothing to name).
  - `assign_province_name(state, coord, rng)` is idempotent (an
    already-named province's name is returned unchanged, not re-rolled)
    and prefers a name not already used anywhere in `state.provinces`,
    falling back to reuse only once a terrain's own pool is exhausted --
    this collision-avoidance rule is this project's own design choice,
    not sourced from anywhere, since the real engine never had to make
    this decision at runtime either. Raises `KeyError` for an unknown
    coord and `ValueError` for `Terrain.NO_TERRAIN`, both real modeling
    invariants.
  - Non-breaking: full suite passed unchanged (2081 passed) before the
    new Phase 152 tests were written. 9 new tests added (2090 passed
    total) in `tests/test_province_names.py` and
    `tests/test_rename_province.py`.
- **Phase 153**: documentation-only correction, no code changed. While
  investigating what became Phase 154, direct code inspection showed
  `turn/search_execution.py execute_search()` (Phase 132) and
  `turn/trade_execution.py execute_give()` (Phase 132/133) were already
  real, `GameState`-mutating execution, but this file's own "Not yet
  implemented" section had never been updated when either landed --
  still listing SEARCH, TRADE, and (checking further) CAST's other
  spells, USE_MI, CHALLENGE/PURSUE, ASPY, and TRAIL as decode-only.
  Corrected the summary bullet and Search's/Trade's own sub-bullets to
  reflect current status, striking through the stale claims rather than
  leaving them to mislead a future reader (same policy as Phase 55's
  own self-correction note above). Suite unchanged (2090 passed).
- **Phase 154**: `models/monster.py MonsterCombatStats`/
  `MONSTER_COMBAT_STATS` (new) -- closes the "only 6 of 61 monster
  species have combat stats" limitation `search_execution.py`'s own
  docstring flagged, the genuine remaining gap Phase 153's own
  correction surfaced.
  - **Project-original, user-compiled, not a Pascal transcription**:
    `MONSTER_STATS` only covers 6 species because `RULES.AK`'s own
    "Monster Table" is explicitly "a partial listing", and no other
    available source (rulebook, Pascal, or the 10 real move files)
    gives stats for the other 54. The user closed that gap directly --
    the same "user authors replacement content for a confirmed-
    unsourced gap" pattern already used for Phase 148's skill-book
    narrative and Phase 152's province names -- supplying a self-
    compiled document (`Desktop/MOSTRI con statistiche.txt`,
    2026-07-15, confirmed by the user to be their own compilation) with
    Hit Point *ranges*, Melee/Missile Skill and Damage, and Speed for
    all 60 real species.
  - Modeled as a **separate** table from the original, RULES.AK-sourced
    `MonsterStats`/`MONSTER_STATS` -- deliberately not merged into or
    overwriting it, so the one directly-cited Pascal quote stays intact
    and independently verifiable. The two corroborate each other well:
    for 5 of the 6 species both cover, this table's own HP range has
    exactly the same midpoint as `MONSTER_STATS`'s "Average Hit Points"
    (Gryphon/Giant/Gargoyle/Troll/Elasmosaurus). **Spectre is the one
    exception, transcribed as supplied rather than silently
    reconciled**: `MONSTER_STATS` gives 20, but this table's own 12-22
    range midpoints to 17 -- a genuine cross-source discrepancy, left
    open and documented rather than picked over the other.
  - `turn/search_execution.py execute_search()` now draws from
    `MONSTER_COMBAT_STATS` instead of the 6-entry `MONSTER_STATS`,
    rolling actual hit points via
    `rng.randint(*stats.hit_points_range)` at combat time -- the source
    gives a range, not a fixed value, for every species, matching every
    other RNG-driven resolution already in this project. Only
    `Monster.NOMONSTER` (the "no monster" sentinel, not a real species)
    still reports `combat_resolved=False` for missing stats now.
  - **Deliberately not modeled from this same source, out of scope for
    this phase**: the source document also gives, per species, an
    Alignment distribution and a Magic Abilities count, plus flavor-text
    descriptions and four numbered combat footnotes -- Troll regenerates
    1 HP/combat-round (negated by Fireball), dragons/Chimera's missile
    attack is reskinned breath-weapon narration, Giant/Treant/Titan's is
    thrown-boulder narration, and Basilisk/Medusa's is petrifying-gaze
    narration. All four are real mechanics/narrative hooks, not just
    flavor to discard, but each needs a change to `turn/encounter.py`'s
    own combat loop or `report/turn_report.py`'s own renderers beyond
    simple stat population -- left for a future phase, not lost.
  - Non-breaking: full suite passed unchanged (2090 passed) before the
    new Phase 154 tests were written (one pre-existing test,
    `test_execute_search_unsourced_guardian_stats_reports_unresolved`,
    was updated in place -- `Monster.ROC` gained real stats this phase,
    so the test now uses `Monster.NOMONSTER`, the one guaranteed-
    unsourced case, instead). 9 new tests added (2099 passed total) in
    `tests/test_monster.py` and `tests/test_search_execution.py`.
- **Phase 155**: monster missile-attack flavor text (project-
  original) + Troll regeneration (mechanics + narration) -- the four
  numbered footnotes `Desktop/MOSTRI con statistiche.txt` (Phase 154's
  own source) supplies, closing them all at once since none needed
  further research: the exact wording and mechanic were already given.
  - `turn/encounter.py Combatant.regenerates_hp` (new field, default 0
    -- every existing caller unaffected): both `resolve_melee_duel()`
    and `resolve_fire_arrow_duel()` heal a surviving combatant that
    much at the end of each round, uncapped (the footnote gives no
    maximum). `turn/search_execution.py TROLL_REGENERATION_PER_COMBAT_
    ROUND = 1` sets it for a Troll's own monster combatant. **Real,
    sourced, deliberately unwired**: the footnote's own
    FIREBALL-negates-regeneration clause needs to know whether a
    FIREBALL was cast as part of the same Search encounter's own
    Encounter Plan -- blocked on `turn/search_decode.py`'s own confirmed
    gap (a Cast tactic's spell id is still an unresolved raw int), not
    attempted as a guess.
  - `report/turn_report.py` -- six new, single-template (not
    `pick_variant`-list) renderers, project-original, translated from
    the user's own Italian: `render_breath_weapon_hit()`/`_missed()`
    (dragons, Chimera), `render_boulder_throw_hit()`/`_missed()`
    (Giant), `render_petrifying_gaze_hit()`/`_missed()` (Basilisk,
    Medusa), plus `render_troll_regeneration()` for the combat message
    the footnote itself specifies. `missile_attack_flavor(weapon)`
    classifies a monster's own `models/weapon.py MONSTER_RANGED_WEAPON`
    assignment (real, `CTME.PAS`-sourced, Phase 94) into one of the
    three categories, or `None` (falls back to the generic Phase
    111-112 `render_fire_arrow_attack()`/`render_attack_hit()`/
    `render_attack_missed()` triplet).
  - **A genuine, documented cross-source discrepancy, not resolved
    either way**: the footnote says Giant, Treant, *and* Titan all
    throw boulders, but `MONSTER_RANGED_WEAPON` (real, Pascal-sourced)
    gives Titan and Treant both `Weapon.NO_WEAP` -- no ranged attack at
    all -- while only Giant maps to `Weapon.BOULDER`.
    `missile_attack_flavor()` follows the confirmed Pascal-sourced
    weapon table over the footnote's own broader claim, the same
    "don't let a less-rigorously-sourced document silently override
    already-cited Pascal data" policy Phase 154's own Spectre
    hit-point discrepancy used.
  - Non-breaking: full suite passed unchanged (2099 passed) before the
    new Phase 155 tests were written. 17 new tests added (2116 passed
    total) in `tests/test_encounter.py`, `tests/test_turn_report.py`,
    and `tests/test_search_execution.py`.
- **Phase 156**: `report/turn_report.py describe_search()`
  (new) -- the last real-execution action (Hire/Fire/Cast/Use_MI/
  Practice/Give already had one, Phases 142-144) without its own report
  composer, even though `turn/search_execution.py execute_search()`
  has run real combat since Phase 132.
  - Found by re-scanning `SAY.PAS` for Search-specific dispatch past
    `RUMORS.PAS`'s own now-fully-mined `Say_Code` block: `_LSearch:
    FD('fsearch',S_Adv,10)` -> `FSEARCH.X` (5 real templates, the
    Search-attempt opening sentence, e.g. "approached the &, intending
    to root out its mysteries") and `_LSacked` (a single, real,
    hardcoded template for attempting to Search an already-looted
    feature) -- both real and declared, neither with a confirmed live
    dispatch site in the surviving `.PAS` files, the same "the calling
    main program is itself missing" status most templates in this
    module already carry. `render_search_attempt()`/
    `render_search_feature_already_sacked()`.
  - `describe_search()`'s combat-outcome half reuses
    `render_mortally_wounded()` (Phase 112) for a fatal loss --
    personal combat's generic [5.0] death rule. A win or an
    inconclusive fight append nothing further: no sourced "you defeated
    the guardian, the treasure is yours" sentence exists anywhere in
    the available archive -- the same confirmed-absent conclusion
    Phase 148's own research already reached for the adjacent
    skill-book-read moment.
  - **Not wired into `describe_turn_results()`, joining PURSUE/TRAIL/
    TRADE as a fourth structurally unwireable action, for the identical
    reason**: `SearchExecutionResult` carries no `feature_id`, and
    `PhaseDispatchResult` itself discards the original decoded
    `SearchRequest` (the only place a `feature_id` survives) before
    `describe_turn_results()` ever sees the entry. `describe_search()`
    stays directly callable by anyone who still has the original
    `SearchRequest`/`Feature` in hand.
  - Non-breaking: full suite passed unchanged (2116 passed) before the
    new Phase 156 tests were written. 9 new tests added (2125 passed
    total) in `tests/test_turn_report.py`.
- **Phase 157**: Quote of the Week -- `models/quote.py` (new)
  and `report/turn_report.py render_quote_of_the_week()` (new), the
  first item on the report-narrator roadmap Phase 58's own docstring
  laid out ("Quote of the Week first, since `PROSE/QUOTES.X2` needs no
  game-state at all").
  - Sourced from `HostAK/TP/PROSE/QUOTES.X2` (header `"94 2"`: 94
    real-world historical quotes, each a 2-line block) and
    `HostAK/TP/SAY.PAS`'s own `_SQuote` dispatch (~line 1231): prints a
    "Quote of the Week:" header, then looks up block `dex-1000` via the
    general `FD` block reader (`RUMORS.PAS`, ~line 2252, already
    confirmed by Phase 58's own foundation) and prints its two lines as
    separate paragraphs (`Pos('quotes',fn) > 0` is the one place `FD`
    forces a paragraph break after *every* line of a block, not just
    between blocks).
  - **The week-selection formula (`qfact`) is real but not
    reproducible**: it depends on `gdyear`/`gdmonth`/`gdday` (the real
    calendar date the host program was run on) and `startfact[company]`
    (a per-company offset) -- both host-only runtime state with no
    representation in a parsed `AK3__T*.K1` move file and no available
    source for how either is initialized. `models/quote.py` therefore
    stops at the same boundary Phase 150's `rename_home_province()`
    already established for `Read_T1Names`'s own real but unavailable
    `miscfile` format: the quote table and the block-lookup mechanism
    (`quote_of_the_week(index)`) are modeled and real; the caller
    supplies the block index (0-93) directly instead of this project
    guessing at a calendar-driven rotation it can't verify or
    reconstruct.
  - All 94 quote/attribution pairs transcribed verbatim from
    `QUOTES.X2` (machine-diffed against the source file to confirm an
    exact match, not just eyeballed), including source order quirks
    (about a third of the blocks state the speaker before the quote
    rather than as a trailing attribution) left as-is, not normalized.
    These are centuries-old public-domain historical quotations (Louis
    VII, Genghis Khan, Machiavelli, and similar) -- the game's own
    flavor-text data file, not new project-original writing.
  - `render_quote_of_the_week()` does not pass either line through
    `report/prose.py render()`: confirmed empirically that none of the
    94 blocks contain any of that engine's marker characters, so marker
    resolution would be a pure no-op.
  - Non-breaking: full suite passed unchanged (2125 passed) before the
    new Phase 157 tests were written. 9 new tests added (2134 passed
    total) in `tests/test_quote.py` (new) and `tests/test_turn_report.py`.
- **Phase 158**: ARMIES report -- `report/turn_report.py
  describe_armies_report()` (new), a deliberately narrower slice of
  `REPORTS.PAS Rep_Armies` (the real "ARMIES" section of the
  end-of-turn letter report).
  - **Research first identified the real remaining scope, then the
    user confirmed proceeding with a narrower slice** (matching Phase
    59's own precedent): the user asked for FINANCES/PROVINCES/
    CHARACTERS/ARMIES together, but research found `ACost`/`LCost`/
    `Tax_Base`/`Inv_Bonus` (the numeric engine behind FINANCES) and
    `ptax` (the per-province tax rating PROVINCES needs) have **no
    surviving source in any of the 13 available `.PAS` files** --
    confirmed absent, the missing-main-program category. `CHARACTERS`
    (`Rep_Leaders`) is the largest, most state-heavy procedure in the
    archive (alignment-sensing noise formulas, a mercenary standby
    state machine, `lspec` special-ability bitmasks), needing far more
    modeling than a single phase could responsibly add. Only `ARMIES`
    (`Rep_Armies`) turned out to be buildable on data this project
    already fully has (`ArmyType`/`Quality`/`LeaderState.name`/
    `ProvinceState.name`, plus `make_army_name`'s own Phase 149
    designation work) -- confirmed with the user before implementing,
    not silently downscoped.
  - Sourced, verbatim: the "ARMIES" section header (`Expand_Write`)
    and its own two-line opening flavor text, both hardcoded directly
    in `REPORTS.PAS` (~line 1039), not a `PROSE/*.X` template --
    rejoined here as one continuous sentence, the same "flowing prose
    split across two raw `WRITELN` lines" shape the FINANCES/
    PROVINCES/STATE-OF-THE-NATION section openings all share.
  - **What this deliberately excludes from the real `Rep_Armies`, and
    why**: the real procedure's second "Mercenary" pass (independent
    mercenaries visible nearby that the kingdom *could* Recruit) needs
    `Known_Merc`/`Commanded` eligibility state this project's
    `GameState` doesn't track -- only the "Hired" pass (armies the
    kingdom actually owns) is modeled. The real table's "Modified
    Quality" column (`Qual_Modfr`) has no surviving source either
    (same missing-main-program category as `ACost`/`LCost` above) --
    only the plain `Quality` renders. Skeletal-Army units' distinct
    "Skel <designation>" form (`astate[an] = Zomboid`) isn't
    reproduced -- `ArmyState` has no per-army undead/skeletal flag.
    The real table's exact fixed-width column layout isn't reproduced
    either -- a documented, unsourced formatting choice (one readable
    line per army) over guessing at column-width semantics with no
    testable source of truth.
  - Each army's race resolves via `models/army_type.py
    MONSTROUS_ARMY_RACE` (the army type's own fixed race for
    monstrous types, else the owning kingdom's race) -- the same
    interpretation `plan_dispatch._dispatch_recruit`'s own
    `is_army_type_compatible_with_race` already established (Phase
    12/153's own note), not `Mod_ARace`'s own unavailable formula.
  - Non-breaking: full suite passed unchanged (2134 passed) before the
    new Phase 158 tests were written. 8 new tests added (2142 passed
    total) in `tests/test_turn_report.py`.
- **Phase 159**: Trail's partial intelligence payload --
  `turn/trail_execution.py TrailExecutionResult` gains `temper`,
  `treasures_owned`, and `armies_led`, plus a correction of that
  module's own stale docstring.
  - **Self-correction, not new invention**: the module's docstring
    claimed `LeaderState` had no `race`/`temper`/`alignment`/treasure-
    ownership field and that `Temper` had no model at all in this
    project -- all wrong as of this phase. `Temper` has had a real
    model since Phase 82, `LeaderState.temper` has stored real values
    since Phase 139, and the leader-held item registry
    (`GameState.items_held_by()`) has existed since Phase 140. Left
    uncorrected, a future reader would trust a doc comment over the
    actual code -- the same self-correction policy Phase 55/153
    already established elsewhere in this project.
  - `execute_trail()` now populates, on a successful spy: `temper`
    (`target.temper`, `None` if never recorded), `treasures_owned`
    (`GameState.items_held_by(target.leader_id)`), and `armies_led`
    (`GameState.armies_commanded_by(target.leader_id)`, already
    computed once for the catch-up-chance roll and reused rather than
    queried twice).
  - **Still genuinely open, not attempted here**: [3.17]'s remaining
    three named fields -- **Actions** (the target's decoded orders;
    `PhaseDispatchResult` discards the original request before storing
    a result, the same structural gap Phase 151 already named for
    PURSUE/TRAIL/TRADE/SEARCH), **race** (no per-leader field; an
    independent Hero has no kingdom to infer one from, unlike a
    kingdom-affiliated leader), and **alignment** (no per-leader field
    exists anywhere in this project; `KingdomState.alignment` is
    kingdom-level only, and Phase 136's `Align_Est` is an estimate
    formula, not a stored real value). The King-target aggregate case
    ("finances, alliances, enemies and controlled provinces") is also
    not attempted -- its underlying data now exists
    (`KingdomState.treasury`, `GameState.allied_kingdoms`,
    `ProvinceState.owner_kingdom_id`), but assembling and routing that
    aggregate view is a distinct, larger follow-up flagged for a
    future phase, not silently expanded into this one.
  - Non-breaking: full suite passed unchanged (2142 passed) before the
    new Phase 159 tests were written. 5 new tests added (2147 passed
    total) in `tests/test_trail_execution.py`.
- **Phase 160**: a second stale-docstring self-correction,
  found immediately after Phase 159's own -- `turn/
  intelligence_estimate.py` (Phase 136, before `LeaderState.birth_x`/
  `LeaderState.temper` existed) still claimed both fields didn't
  exist. Docstring-only; no code or test changes.
  - `LeaderState.birth_x`'s own docstring correction: the module
    previously said this project had no field for a leader's birth
    coordinate at all. It's had one since Phase 139, and
    `turn/aspy_execution.py`'s own real caller already passes
    `leader.birth_x or 0` into `estimate_temper()`.
  - `LeaderState.temper`'s own correction is only half a stale claim:
    the field is real (Phase 139) and `aspy_execution.py` sources
    `true_temper` straight from `spotted.temper`. But
    `LeaderState.alignment` genuinely still doesn't exist (only
    `KingdomState.alignment` does) -- `aspy_execution.py` approximates
    a spotted leader's true alignment with their kingdom's own, a
    real, still-open simplification distinct from "no field at all."
  - Non-breaking: full suite passed unchanged (2147 passed) -- no new
    tests, docstring-only change.
- **Phase 161**: research-only -- confirmed Hire's own
  "required pay" temper/race/alignment compatibility formula (open
  since Phase 17) has no surviving source at all, and documented that
  finding everywhere the gap was previously described as merely
  "unmodeled."
  - `LCost` -- the one Pascal identifier tied to a Hero's per-turn/
    required pay, cited at four separate sites in `REPORTS.PAS` (the
    FINANCES section total, the CHARACTERS section's own mercenary-
    pay-mention line, and the per-leader ARMIES listing) -- is called
    but never *defined* anywhere in the 13 available `.PAS` files.
    Same missing-main-program category already confirmed for `ACost`/
    `Tax_Base`/`Inv_Bonus` (Phase 158's own note above). No separate
    `Hire`-specific procedure survives either -- only `_LHire`'s own
    narrative dispatch code (`SAY.PAS` -> `acchire.x`, already modeled
    as `render_hire_accepted()`, Phase 114) exists in the archive.
  - Recurring per-gameturn pay and alignment-based hire refusal share
    the same fate -- neither has any surviving source, not merely
    still unsearched.
  - Updated three sites that previously described this as "unmodeled"
    without saying whether a source existed to model it from:
    `turn/plan_dispatch.py`'s own HIRE/FIRE note, `models/temper.py`'s
    own docstring, and this README's own Phase 17 entry and "Not yet
    implemented" section.
  - Docstring/README-only change; no code or test changes. Full suite
    passed unchanged (2147 passed).
- **Phase 162**: designs and implements Hire's real
  required-pay formula, closing the gap Phase 161 confirmed has no
  surviving Pascal source -- authorized directly by the user, who
  quoted the real player's manual text for Hire Hero ([3.5]) and
  instructed this project to design an algorithm from alignment
  distance and temperament, capped at 5 gold (unhireable without Charm
  or Resurrection, since the Hire action's own offer ceiling is 4).
  - **A pre-existing bug found and fixed along the way**:
    `models/alignment.py`'s own `Alignment` enum declaration order
    (`DIVINE, GOOD, NEUTRAL, EVIL, ANTI_HOLY, PAGAN, DRUID, UNDEAD,
    MECHANICAL, SPECIAL` -- chosen, Phase 4/80, to match display
    strings) does not match the real Pascal `outlook` ordinal sequence
    (`Heavenly=0, Good=1, Druidic=2, Worldly=3, Animal=4, Evil=5,
    Hellish=6, Undead=7, Mechanical=8, Special=9`, already quoted in
    that module's own docstring). `turn/intelligence_estimate.py`'s
    `estimate_alignment()` had used `tuple(Alignment)` -- the wrong,
    declaration-order sequence -- for its own real `Align_Est`
    ordinal-nudge formula since Phase 136. New `ALIGNMENT_ORDINAL`/
    `ALIGNMENT_BY_ORDINAL` (`models/alignment.py`) supply the correct
    mapping; `estimate_alignment()` now uses it. Confirmed load-bearing
    by cross-checking the user's own hard data point: "a Good King
    generally cannot hire a Pagan Hero" is only true (distance 3) at
    the real ordinals, not the declaration-order ones.
  - **`turn/hire_pay.py`** (new): `required_pay(hero, king) -> int`,
    an integer 1-5. `align_distance` (real `ALIGNMENT_ORDINAL` gap,
    0 if either side's alignment is unrecorded) maps to a base pay of
    1/2/3 for distances 0/1/2, or straight to 5 for distance >= 3 --
    deliberately skipping 4, so the anchor case (Good King, Pagan Hero,
    distance 3) reproduces exactly as "generally cannot hire" rather
    than merely "expensive." A temper mismatch (`LeaderState.temper`,
    Phase 139) adds +1, capped at 5; missing temper data defaults to
    "same" (the permissive case), the same convention this project
    already uses for other unset per-leader fields.
  - **`LeaderState.alignment: Alignment | None = None`** (new field,
    `models/game_state.py`) -- mirrors `.temper`'s own Phase 139
    precedent. Previously only `KingdomState.alignment` (kingdom-level)
    existed; this is the first per-leader alignment field, and
    `turn/hire_pay.py` is its first real consumer.
  - **`turn/plan_dispatch.py _dispatch_hire()` rewritten**: looks up
    the kingdom's own King (`LeaderState.is_king`, the same idiom
    `battle_orchestrator.py` already uses), computes
    `required_pay(hero, king)`, and charges *that* amount rather than
    the raw `request.gold_offer`. Refuses outright
    (`reason="alignment gap too wide"`) when `pay >= 5` -- unreachable
    via any legal <=4-gold offer -- or issues a real price counter-offer
    (`reason="offer below required pay"`) when the offer is below the
    computed pay. `HireExecutionResult` gained `minimum_gold: int |
    None`, set whenever pay was actually computed. Recurring per-turn
    pay stays unmodeled (no sourced formula for it either, matching
    Recruit's own established one-time-charge simplification).
  - **`report/turn_report.py describe_hire()` unblocked**: the two
    Phase 114 renderers that had no real trigger under the old
    "always accept if affordable" simplification now have one --
    `render_hire_refused` (`REFHIRE.X`) on `"alignment gap too wide"`,
    `render_hire_counter_offer` (`_LCounter`) on `"offer below required
    pay"`, using the new `minimum_gold`.
  - Two pre-existing tests updated for the new charged-amount behavior
    (`test_dispatch_hire_assigns_independent_hero_and_debits_treasury`:
    treasury delta 3->1, since neither side had a recorded alignment/
    temper in that fixture; `test_dispatch_hire_fails_on_insufficient_
    treasury`: starting treasury lowered from 2 to 0, since 2 gold is
    now enough to cover the default pay of 1). Two `test_intelligence_
    estimate.py` expectations updated for the ordinal-order fix
    (GOOD-nudged-up now lands on `DRUID`, the real next ordinal, not
    `NEUTRAL`).
  - 18 new tests: `ALIGNMENT_ORDINAL`/`ALIGNMENT_BY_ORDINAL`
    (`tests/test_alignment.py`), `required_pay()`
    (`tests/test_hire_pay.py`, new file), the three new
    `_dispatch_hire()` outcomes and `describe_hire()`'s two newly
    reachable renderers. Full suite: 2165 passed (2147 unchanged +
    18 new).
- **Phase 163**: revises Phase 162's own temper weighting,
  per direct user feedback the same day: "il temperamento deve contare
  meno della differenza di allineamento -- direi della metà" (temper
  must count for less than alignment distance -- about half).
  - Phase 162's original formula added a flat +1 gold for a temper
    mismatch unconditionally, at every alignment distance -- the exact
    same per-step weight as one full alignment-distance step, not
    "half" of anything.
  - Since a Hero's temper is a boolean match/mismatch (no intermediate
    steps the way alignment distance has), there's no literal
    fractional gold to charge for "half a step." Instead, `turn/
    hire_pay.py required_pay()` now demotes temper to a *secondary
    amplifier*: a mismatch only raises the price when some alignment
    friction already exists (`align_distance >= 1`) -- it never moves
    the price on its own when the Hero's alignment already matches the
    King's exactly (`align_distance == 0`). This halves temper's
    practical influence in the cleanest available integer-gold sense
    (it now affects 2 of the 3 non-unhireable distance brackets instead
    of all 3, each still by the same +1 as before) rather than trying
    to approximate a literal "0.5 gold" through rounding.
  - One pre-existing test's expectation flipped (same alignment,
    different temper: 2 -> 1) and was renamed to reflect the new "no
    effect at distance 0" behavior; one new test added confirming
    temper still adds +1 once real alignment friction exists (distance
    1). Full suite: 2166 passed (2165 unchanged + 1 new).
- **Phase 164**: closes another slice of Trail's own
  ``[3.17]`` intelligence-payload gap -- ``TrailExecutionResult.alignment``,
  directly enabled by Phase 162's new ``LeaderState.alignment`` field
  (added for ``turn/hire_pay.py``, not originally for Trail). When
  Phase 159 first populated `temper`/`treasures_owned`/`armies_led`, no
  per-leader alignment field existed anywhere in this project yet
  (only kingdom-level ``KingdomState.alignment``, and Phase 136's own
  ``Align_Est`` is an *estimate* formula, not a stored real value) --
  that gap is now closed as a direct side effect of unrelated work,
  the same "narrows a docstring-flagged gap in passing" pattern this
  project has used repeatedly (e.g. Phase 159 itself, for Trail's own
  temper field).
  - ``execute_trail()`` now sets ``TrailExecutionResult.alignment =
    target.alignment`` on a successful spy -- ``None`` if never
    recorded, the same convention `temper` already uses. Deliberately
    reads the target's *real* stored alignment, not Phase 136's
    imperfect-information `Align_Est` estimate (a different, ASpy-only
    mechanic for a different in-game situation -- a Trail spy learns
    the truth, per [3.17]'s own wording, "gaining information on the
    character's... alignment").
  - Of [3.17]'s six named intelligence fields, only two remain
    genuinely open: Actions (needs `PhaseDispatchResult` to retain the
    target's own decoded request, a larger structural change) and race
    (`LeaderState` still has no per-leader race field, and an
    independent Hero has no kingdom to approximate it from).
  - 2 new tests (`test_execute_trail_success_reports_targets_alignment`,
    `..._reports_none_alignment_when_not_recorded`); the existing
    failure-path test extended to also assert `alignment is None`.
    Full suite: 2168 passed (2166 unchanged + 2 new).
- **Phase 165**: closes Trail's own race field too, per
  direct user instruction ("continua con la razza in Trail") --
  `TrailExecutionResult.race`, the last field this project can source
  of [3.17]'s six named intelligence fields (only Actions remains
  genuinely open, blocked on a separate structural gap -- see the
  module docstring).
  - No per-leader race field was added to `LeaderState` -- there is no
    source distinguishing an individual character's race from their
    Kingdom's own. Instead reuses the same approximation `report/
    turn_report.py describe_armies_report()`'s own Phase 158 note
    already established for `MONSTROUS_ARMY_RACE`-less army types:
    `KingdomState.race`, looked up via the target's own `kingdom_id`.
  - An independent Hero (`kingdom_id is None`) genuinely has no
    kingdom to infer a race from -- reported as `None`, the same
    convention every other field here uses, rather than guessing.
    This does leave exactly the case [3.17] itself calls out most
    ("if the character is a King...") with real data.
  - 2 new tests (`test_execute_trail_success_reports_targets_race_via_kingdom`,
    `..._reports_none_race_for_an_independent_hero`); the existing
    failure-path test extended to also assert `race is None`. Full
    suite: 2170 passed (2168 unchanged + 2 new).
- **Phase 166**: closes [3.17]'s King-target aggregate case
  in Trail -- "If the character is a King, some information may be
  gained concerning the finances, alliances, enemies and controlled
  provinces of the Kingdom." Unlike Actions (the one field that stays
  genuinely open, see the module docstring), this data all already
  existed on `GameState` -- `KingdomState.treasury`, `GameState.
  is_allied()`, `ProvinceState.owner_kingdom_id` -- so no new data
  model was needed, only a new result type to carry it.
  - New `KingIntelligence` dataclass (`turn/trail_execution.py`):
    `treasury`, `allied_kingdom_ids` (computed by checking every other
    registered kingdom against `GameState.is_allied()` -- no bulk
    "all allies of X" helper existed to reuse), `controlled_provinces`
    (every `ProvinceState` whose `owner_kingdom_id` matches).
    `TrailExecutionResult.king_intelligence` is populated only when
    `target.is_king` is `True`, `None` otherwise -- matches the
    rulebook's own "if the character is a King" conditional exactly.
  - **"Enemies" is deliberately excluded from `KingIntelligence`.**
    This project has no positive enemy/hostile-diplomacy registry --
    only `GameState.allied_kingdoms`, a registry of *friendly* pairs.
    Treating "not allied" as "enemy" would misclassify every
    merely-unknown or neutral kingdom as hostile -- worse than
    reporting nothing, since it would silently invent a diplomatic
    stance with no source. Same reasoning already applied to `LCost`/
    `Ofc_Pts` elsewhere in this project: confirmed absent, not
    guessed at.
  - 2 new tests (`test_execute_trail_success_reports_king_intelligence_for_a_king_target`,
    `..._reports_none_king_intelligence_for_a_hero_target`); the
    existing failure-path test extended to also assert
    `king_intelligence is None`. Full suite: 2172 passed (2170
    unchanged + 2 new).
- **Phase 167**: implements Practice's own [6.1] Tactical
  army-training mechanic, previously a bare
  `not_implemented_for_ability=True` stub -- the user asked to continue
  with whichever well-scoped gap this session judged best; research
  identified this as closable now with two real sourced percentages
  and a direct precedent (`cast_execution.py`'s own Oratory
  quality-bump handler).
  - `turn/practice_decode.py`'s own [6.1] quote gives exactly two of
    `Quality`'s five upward transitions a real percentage:
    Green->Average 25%, Crack->Elite 0.2%. **The other three
    (Depleted->Green, Average->Veteran, Veteran->Crack) are
    deliberately left unmodeled** -- interpolating three more
    percentages from two anchors describing two *structurally
    distinct* transitions (not two points on one curve, unlike
    `win_probability`/`exploration_advantage_multiplier`'s own
    accepted interpolations) would be a materially larger, far less
    constrained guess than anything already accepted in this project.
    New `TACTICAL_TRAINING_CHANCE` (`turn/practice_execution.py`) only
    has entries for `Quality.GREEN`/`Quality.CRACK`.
  - New `execute_practice_tactical(state, leader_id, rng)`: for each of
    the practicing leader's own commanded armies (`GameState.
    armies_commanded_by`) at a sourced tier, rolls it upward if gated
    on the rulebook's own "if a higher-quality army is present to
    'train and inspire' it" condition -- interpreted here as *any
    other army under that same leader's command* having a strictly
    higher *original* `Quality` (a snapshot taken before any rolls
    this call, so results don't depend on iteration order) -- an
    interpretation, not a literal quote, but grounded directly in the
    condition's own wording.
  - `execute_practice()`'s `Ability.TACTICAL` branch now routes here
    instead of returning the old stub; `PracticeExecutionResult`
    gained `trained_army_ids: tuple[int, ...] = ()`.
    `execute_practice_group()`'s own TACTICAL branch is unchanged
    (still `not_implemented_for_ability=True`) -- **multi-leader army
    pooling stays out of scope**, since co-located *characters*
    pooling their *personal skill* rolls (the existing group mechanic)
    doesn't apply to Tactical's *army*-training mechanic at all;
    flagged as a further future phase.
  - 1 pre-existing test updated (Tactical no longer returns
    `not_implemented_for_ability=True`) + 7 new tests covering the
    training roll, the "no higher-quality army present" gate, the two
    sourced tiers, untrainable tiers left alone, and armies commanded
    by someone else being ignored. Full suite: 2179 passed (2172
    unchanged + 7 new).
- **Phase 168**: `ProvinceState.terrain_override` (Part Sea/
  Flood, Phase 59) had zero gameplay consumers anywhere in the codebase
  -- confirmed by an exhaustive grep sweep finding it was only ever
  written by the two spells that set it, never read by any real
  mechanics. The user picked this as the recommended next gap
  ("terrain_override non collegato").
  - New `ProvinceState.effective_terrain()` (`models/game_state.py`):
    returns `terrain_override` if set, `terrain` otherwise -- the
    province's real current terrain for gameplay mechanics.
    Deliberately distinct from `illusory_terrain` (Illusory Terrain):
    that field only deceives what an outside observer is *told*, and
    must never feed into a real mechanics calculation -- conflating the
    two would let a bluff spell silently change real movement costs or
    combat outcomes. `illusory_terrain` is untouched by this phase.
  - Wired into every real-mechanics call site found across two
    successive grep sweeps (the second caught call sites the first
    "obvious" pass missed):
    - `turn/battle_orchestrator.py fight_battle()`: a local
      `terrain = province.effective_terrain()` now feeds combat
      ability selection, `_build_battle_units`, `_apply_pursuit`,
      `_whale_forced_retreat_applies`, and `_fleet_avoids_elimination`
      (previously all read `province.terrain` directly).
    - `turn/move_execution.py`: `record_kingdom_exploration()`'s
      terrain-dependent Basic Exploration Number, `execute_move()`'s
      `target_terrain` for `resolve_move()`, and its `is_sea_province`
      flag for `movement_cost_for_move()`.
    - `turn/plan_dispatch.py`: the EXPLORE branch's `resolve_explore()`
      call.
    - `turn/turn_processor.py`: the same `target_terrain`/
      `is_sea_province` pair as `move_execution.py`, for its own
      `resolve_move()`/`movement_cost_for_move()` calls.
    - `turn/cast_execution.py`: three eligibility checks that used to
      read the raw base terrain -- `_execute_part_sea()` (now correctly
      targetable on a province Flooded to Sea), `_execute_flood()` (now
      correctly rejects a province already Flooded to Sea via
      override), `_execute_earthquake()` (now correctly rejects a
      province Flooded to Sea even though its base terrain is still
      land).
  - **Deliberately not touched**: `turn/rename_province.py` (reads
    `province.terrain` for its name-pool lookup -- flavor/naming, not a
    gameplay mechanic, out of scope for this phase).
  - 3 new tests for `effective_terrain()` itself
    (`tests/test_game_state.py`); 2 new tests for `move_execution.py`
    (exploration's Basic Exploration Number and conquest's sea-battle
    movement surcharge both honoring the override); 1 new test for
    `battle_orchestrator.py` (Fleet's land-only Depleted carve-out
    correctly not applying in an override-Sea battle); 3 new tests for
    `cast_execution.py` (Part Sea/Flood/Earthquake eligibility all
    reading the effective terrain). Full suite: 2188 passed (2179
    unchanged + 9 new).
- **Phase 169**: implements Search's own [5.6] Flee tactic,
  previously reported as an honest `combat_resolved=False` alongside
  Fire Arrow/Scout/Steal-only plans. Research (an Explore-agent report on
  candidate next phases) surfaced this as the recommended, narrowest-
  scoped gap: no new data model needed, and the exact three percentages
  were already sourced and transcribed in `models/monster.py`'s own
  [5.6] quote, just never consumed anywhere.
  - Rulebook [5.6], quoted in full in `turn/search_execution.py`'s own
    new addendum: "The character can declare to prefer flight over
    combat. The chance of fleeing from fast monsters is 20%, from
    medium-speed monsters or other characters 50%, and slow monsters can
    be escaped from 80% of the time." New `FLEE_CHANCE: dict[
    MonsterSpeed, float]` (`turn/search_execution.py`) keyed by the same
    `MonsterSpeed` tier `models/monster.py MONSTER_COMBAT_STATS` already
    carries per species.
  - `execute_search()`: a `Maneuver.FLEE` tactic anywhere in the
    Encounter Plan is rolled *before* Melee -- matching the rulebook's
    own tactic-sequencing advice ([5.8]: "follow it with a Flee order
    and/or a [Scout] order"), i.e. Flee is a first attempt to avoid the
    fight, not a last resort after losing it. A successful roll ends the
    Search with no combat and no loot (`SearchExecutionResult` gained
    `fled: bool = False`); a failed roll falls through to whatever the
    rest of the plan specifies (Melee, if present), exactly as before
    this phase.
  - **Deliberately excluded, not guessed**: the Cauto/Codardo
    temperament's "+30% chance to flee" bonus ([5.6]'s own "(NOVITA')"
    addendum) and Invisibility's "+30% chance to flee" bonus
    (`turn/cast_execution.py`'s own docstring, already flagged unmodeled
    since it needs the not-yet-built Cast-tactic combat engine) -- both
    are real, sourced modifiers to this same roll, but adding either now
    would be an under-tested compound change; flagged as a natural
    follow-up phase instead.
  - 4 new tests (`tests/test_search_execution.py`): `FLEE_CHANCE`'s
    exact three values cross-checked against real species (Gryphon/
    Gargoyle/Golem), a successful flee ending the Search with no combat,
    a failed flee falling through to Melee, and a Melee-only plan never
    consuming a flee roll even when the very first scripted roll would
    satisfy the chance. Full suite: 2192 passed (2188 unchanged + 4
    new).
- **Phase 170**: implements Search's own [5.2] Fire Arrow
  tactic, previously left unwired specifically because "nothing in any
  available source says a monster's own `missile_skill` drives an
  equivalent formula" -- reversing that exclusion, since `models/
  monster.py`'s own Monster Table quote sits directly beneath [5.2]'s
  formula and gives every species an explicit Missile Skill/Damage
  column, which *is* that source.
  - **Encounter Plan tactics now execute in strict list order (a
    correction to Phase 169's own design)**: Regolamento AK.txt's own
    worked example ([11.3], "ESEMPI DI PIANI D'INCONTRO") -- "FI, FL.
    Significato: Tirare con l'Arco, poi fuggire" ("Shoot with the bow,
    then flee") -- proves tactics run in the order listed, each one
    attempted until it resolves the encounter or exhausts, before
    falling through to the next. Phase 169 had rolled `Maneuver.FLEE`
    unconditionally *before* Melee regardless of its position in the
    plan; that only ever matched by coincidence (every tested plan
    happened to list Flee before Melee already). `execute_search()` is
    rewritten to walk `request.tactics` in order; unwired tactics
    (Steal, Talk, Say, Give, Fulfill, Scout, Cast, Use_MI, Beg) are
    silently skipped mid-walk rather than aborting it, matching how real
    plans mix wired and unwired tactics (e.g. [11.3]'s own
    "ST, CA-FI, ME, SC").
  - `turn/encounter.py`: new `Combatant.missile_damage_range` (default
    `FIRE_ARROW_DAMAGE_RANGE`, mirroring `melee_damage_range`'s own
    Phase 132 precedent) lets a monster combatant supply its own Fire
    Arrow damage die from `models/monster.py MonsterCombatStats
    .missile_damage`; `roll_fire_arrow_attack()`/`resolve_fire_arrow_duel()`
    now read each attacker's own field instead of the module-level
    constant.
  - `turn/search_execution.py`: `_leader_combatant()` now also reads
    `Ability.ARCHERY`; the monster `Combatant` gets
    `archery_skill=stats.missile_skill` and `missile_damage_range=
    stats.missile_damage` (falling back to `FIRE_ARROW_DAMAGE_RANGE`
    when `None`, i.e. an unarmed species like Gargoyle). A monster with
    `missile_skill=0` simply gets zero free attacks
    (`fire_arrow_free_attacks(0) == 0`) -- a natural formula consequence,
    not a special-cased exclusion.
  - 3 new tests in `tests/test_encounter.py` (missile damage range
    defaults, `roll_fire_arrow_attack`'s custom range, `resolve_fire_arrow
    _duel` honoring each combatant's own die) and 7 new tests in
    `tests/test_search_execution.py` (Fire Arrow win/loss, exhaustion
    falling through to Melee, the real "Shoot then Flee" ordering
    example, an unwired tactic being skipped mid-plan, and the monster
    combatant correctly carrying `missile_skill`/`missile_damage` from
    `MONSTER_COMBAT_STATS`, including the unarmed-species fallback). 2
    pre-existing tests updated for the new tactic-walk order (padding
    for the monster's hit-points draw now running before the flee roll)
    and the generalized "no wired tactic" reason string. Full suite:
    2202 passed (2192 unchanged + 10 new).
- **Phase 171**: implements Practice's own Sageness
  device-discovery roll ([4.3.1], the rulebook's own heading is
  "CONOSCENZA -- Sageness [SA]", not the "[4.31]" citation this
  project's own research report used to flag the gap -- corrected here
  against the real section number). `turn/practice_execution.py`'s own
  docstring had already flagged this as sourced-but-unimplemented,
  blocked only because "this project has no data model for what a
  discovered device even is or does" -- closable now as a flag with no
  further consequence, the same pattern already used elsewhere in this
  project for a roll whose downstream effect isn't modeled yet.
  - Rulebook [4.3.1], quoted in full in the module's own new addendum:
    "Permette la scoperta di nuovi strumenti o conoscenze. Quando si fa
    pratica in questo Talento (Practice Sageness) c'e un 5% di
    probabilita per livello di inventare o scoprire qualcosa di
    utile... Se un personaggio con un livello di abilita 4 pratica il
    Talento Sageness tutte le fasi, in media fara una scoperta ogni
    turno." New `SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL = 0.05`.
  - `execute_practice()`: for `Ability.SAGE`, an *independent* roll ("on
    top of, not instead of" the ordinary [3.13] skill-rise roll this
    module already resolves) against `current_skill *
    SAGE_DEVICE_DISCOVERY_CHANCE_PER_LEVEL` sets a new
    `PracticeExecutionResult.device_discovered` flag. Uses the
    *pre*-attempt skill level (not any same-phase rise) -- the
    rulebook's own worked example holds skill fixed at 4 throughout,
    giving no basis to prefer the post-rise level. Rolled *after* the
    ordinary skill-rise attempt -- an unsourced but inconsequential
    ordering choice, since the two rolls are independent either way.
  - **What the roll doesn't do**: the discovered device itself stays
    entirely unmodeled -- no item/inventory/effect system exists
    anywhere in this project (same gap `turn/search_execution.py`'s own
    [5.9] addendum already documents for a Search's looted treasure).
    **Not extended to `execute_practice_group`**: the multi-character
    pooling path resolves a *shared* skill-rise outcome, but Sageness's
    device-discovery roll is a per-character mechanic with no stated
    group interaction -- flagged as a further future phase, the same
    "don't silently expand scope" precedent Phase 167 set for
    Tactical's own group-pooling gap.
  - 3 pre-existing tests updated (`Ability.SAGE` was already used in them
    as an arbitrary example ability; each now pads its `ScriptedRandom`
    for the extra roll SAGE now consumes) plus 1 in
    `tests/test_turn_processor.py` (same padding, for a co-located,
    different-ability Practice pair). 6 new tests in
    `tests/test_practice_execution.py`: the 5%-per-level constant, a
    successful discovery, a failed one, the 0%-at-skill-0 edge case, the
    pre-attempt-skill-level ordering (rejects the post-rise level via a
    roll that would only succeed under the wrong one), and a non-Sage
    ability never consuming the extra roll at all. Full suite: 2208
    passed (2202 unchanged + 6 new).
- **Phase 172**: implements Use_MI's wand charge decrement,
  previously flagged as an honest "not modeled" gap in `turn/
  use_mi_execution.py`'s own docstring ("this project has no sourced
  per-cast decrement rule"). Closable now: `PROSE/TREASURE.X2`'s own
  description, identical across all 20 spell-casting wands (e.g. the
  Wand of Fire's own entry), gives exactly the rule that was missing:
  "There is a certain number of charges in this item, and each time you
  cast the spell you use up a charge. When all charges are used up, the
  item becomes useless."
  - `execute_use_mi()`'s `SPELL_WAND` branch: an item at `charges <= 0`
    is rejected outright ("becomes useless"), *before* attempting the
    cast at all -- `reason="item has no charges remaining"`. Otherwise
    the cast proceeds as before (Phase 141's own automatic-success,
    skill-2 wand rules), and `ItemInstance.charges` (`trcharges`, Phase
    140) is decremented by exactly 1, but **only when the cast
    genuinely happens** (`cast_result.applied is True`) -- a validation
    failure ("target not found", out of range, etc.) never reaches the
    spell's own success rule in the first place, so nothing was
    actually "cast" and no charge is spent.
  - 3 pre-existing tests updated to supply `charges=1` (they previously
    relied on `ItemInstance.charges`' own default of `0`, which the new
    zero-charges precondition now correctly rejects).
  - 4 new tests in `tests/test_use_mi_execution.py`: a successful cast
    decrementing charges by exactly 1, a zero-charge item rejected
    before any cast is attempted, a validation failure leaving charges
    untouched, and a wand becoming genuinely useless (its second Use_MI
    attempt rejected) immediately after its last charge is spent. Full
    suite: 2212 passed (2208 unchanged + 4 new).
- **Phase 173**: closes `turn/encounter.py`'s own two
  remaining flagged Fire Arrow gaps -- **documentation-only, no
  behavior change** (both were already correctly implemented; the
  design just lacked a citable source). Closed directly by the user
  (project author), the same "author-supplied rulebook content"
  pattern already used for Phase 162's Hire-pay formula and Phase 163's
  temper-weight correction: "Si puo dare un solo ordine di FI durante
  un piano speciale di incontro. Una volta usato, si esauriscono le
  frecce e i combattenti passano alla fase successiva che dipende
  dall'elenco di ordini messi nel piano d'incontro, che quindi puo
  essere un CA (cast a spell) oppure ME oppure FL." ("Only one FI
  order can be given in a Special Encounter Plan. Once used, the
  arrows run out and combatants move to the next phase, determined by
  the tactic list in the Encounter Plan, which can then be CA/Cast,
  ME/Melee, or FL/Flee.")
  - **"About double" free attacks when both combatants have Archery**
    ([5.2]) -- confirmed not a real gap: since only a single Fire Arrow
    order can ever appear in a plan, the "if two characters with
    archery skill fight each other" doubling clause never actually
    applies to how a single `FI` tactic resolves.
    `resolve_fire_arrow_duel` already correctly uses each combatant's
    own, undoubled `archery_skill` free-attack count.
  - **What happens after Fire Arrow's free attacks run out with nobody
    dead** ([5.2]) -- confirmed: `resolve_fire_arrow_duel`'s own
    `winner=None` is exactly the "fall through to the plan's next
    tactic" signal `turn/search_execution.py`'s own Phase 170
    tactic-walk already reads it as. That design (built and tested in
    Phase 170, before this confirmation existed) turns out to already
    match the real rule exactly.
  - `turn/encounter.py`'s module docstring and `resolve_fire_arrow_duel`'s
    own docstring rewritten to cite this directly instead of describing
    both as open, unsourced gaps; `turn/search_execution.py`'s own
    "strict list order" section cross-references the same confirmation.
  - No new tests: both mechanics were already exercised
    (`test_resolve_fire_arrow_duel_no_kill_when_free_attacks_run_out`,
    `test_execute_search_shoot_tactic_exhausted_falls_through_to_melee`)
    -- only their surrounding documentation changed. Full suite: 2212
    passed, unchanged.
- **Phase 174 (research only, no code changes)**: the user pointed out
  a stale earlier survey's claim that `models/monster.py` had "55 of 61
  species without combat stats." Direct re-reading of `Desktop/MOSTRI
  con statistiche.txt` plus `grep -c` against `MONSTER_COMBAT_STATS`
  confirmed that claim was simply wrong -- it conflated
  `MONSTER_COMBAT_STATS` (60 real species, all present since Phase 154)
  with the unrelated, deliberately-small `MONSTER_STATS` (6 entries).
  No gap existed to close; nothing was implemented, no README entry's
  own scope changed, no commit made. The same research did confirm the
  file's Alignment/Magic-Abilities columns and four numbered combat
  footnotes (Troll regeneration -- already wired, Phase 155; dragon/
  Chimera breath; Giant/Treant/Titan boulder; Basilisk/Medusa
  petrifying gaze) remain genuinely unmodeled -- see Phase 175 below
  for the narrative-footnote half of that list.
- **Phase 175**: wires the three species-specific missile-
  attack narration variants (dragon/Chimera breath weapon, Giant
  boulder throw, Basilisk/Medusa petrifying gaze) from `Desktop/MOSTRI
  con statistiche.txt`'s own four numbered footnotes into Search's Fire
  Arrow combat, closing the gap Phase 174 re-confirmed. Authorized by
  the user: "procedi con le note narrative sul missile."
  - **Orphaned-but-complete infrastructure discovery**: the six
    renderer functions this phase needed (`render_breath_weapon_hit/
    missed`, `render_boulder_throw_hit/missed`,
    `render_petrifying_gaze_hit/missed`) and their dispatcher
    (`missile_attack_flavor(weapon) -> str | None`) already existed,
    fully implemented and documented, in `report/turn_report.py` since
    Phase 155 -- but had no call site anywhere in `src/`. The real
    missing piece was a per-shot Fire Arrow attack log, which nothing
    in the project had ever built.
  - `turn/encounter.py`: new `FireArrowShot` dataclass
    (`{shooter: "a"/"b", hit: bool, damage: int}`) and a `shots: tuple
    [FireArrowShot, ...] = ()` field on `EncounterCombatResult`
    (empty for every Melee duel and every pre-Phase-175 caller).
    `resolve_fire_arrow_duel()` now appends one `FireArrowShot` per
    shot fired by either combatant, in real firing order, and returns
    the full log in all three of its return paths.
  - `turn/search_execution.py`: `SearchExecutionResult` gains
    `fire_arrow_shots: tuple[FireArrowShot, ...] = ()` and
    `guardian_monster: Monster | None = None`. `execute_search()`'s
    tactic walk copies the Shoot tactic's own shot log out and attaches
    both fields to whichever result the walk eventually returns --
    the Shoot tactic's own terminal outcome, a later Melee tactic's
    outcome (if Fire Arrow ran out first without a winner), or the
    walk-exhausted fallback -- so a shot fired earlier in the plan is
    still narrated even when it didn't decide the fight.
  - `report/turn_report.py describe_search()`: now renders each shot in
    `result.fire_arrow_shots`, in order, right after the opening
    `_LSearch` line. Only the guardian's own shots (`shooter == "b"`)
    are checked against `missile_attack_flavor(MONSTER_RANGED_WEAPON
    .get(result.guardian_monster))` for a flavored renderer; the
    leader's own shots (`shooter == "a"`) always use the generic
    `render_fire_arrow_attack()`/`render_attack_hit()`/
    `render_attack_missed()` triplet (Phase 111-112), matching the
    user's own footnote wording ("cosa viene scritto quando parte il
    missile [del mostro]" -- what gets written when the *monster's*
    missile is fired). A monster with no flavor mapping (`missile_
    attack_flavor()` returns `None`) also falls back to the generic
    triplet for its own shots -- this includes Titan/Treant, `models/
    weapon.py`'s own deliberately-preserved discrepancy (Phase 94):
    both map to `Weapon.NO_WEAP`, not `Weapon.BOULDER`, even though the
    user's own footnote names Giant/Treant/Titan together for the
    boulder throw. That discrepancy is left exactly as-is, not "fixed"
    by overriding the Pascal-sourced weapon table.
  - 15 new tests: `tests/test_encounter.py` (+4, per-shot logging and
    firing order, Melee never logs shots), `tests/test_search_execution
    .py` (+4, the new fields surviving onto every terminal-result shape
    the tactic walk can produce), `tests/test_turn_report.py` (+7,
    each of the three flavored renderer families dispatching correctly,
    the leader's own shot always using the generic triplet even against
    a flavored monster, the Titan discrepancy falling back to generic,
    and shot narration ordering before a fatal `render_mortally_wounded
    ()` line). Full suite: 2227 passed (2212 unchanged + 15 new).
- **Phase 176**: closes `Desktop/MOSTRI con statistiche.txt`'s
  Alignment-distribution column ("Neutral (50%) / Pagan (50%)") for all
  60 real monster species. Authorized directly by the user: "Colmiamo
  il gap: Distribuzione di Allineamento per specie... Ogni volta che si
  crea il mondo e si piazzano i mostri per quelli che hanno due o tre
  allineamenti si tirano le percentuali e si assegna l'allineamento"
  ("Every time the world is created and monsters are placed, for those
  with two or three alignments, the percentages are rolled and the
  alignment is assigned").
  - `models/monster.py`: new `AlignmentOption` (`{alignment, percent}`)
    and `MONSTER_ALIGNMENT_DISTRIBUTION: dict[Monster, tuple[
    AlignmentOption, ...]]`, covering all 60 real species (matching
    `MONSTER_COMBAT_STATS`'s own coverage, `Monster.NOMONSTER` excluded)
    with each species' own tuple summing to exactly 100.
  - New `roll_monster_alignment(monster, rng) -> Alignment | None`. Per
    the user's own wording, **the roll only happens for a 2-or-3-option
    species** -- a single-option species (e.g. Gryphon: Neutral, no
    percentage shown in the source) returns that one `Alignment`
    directly without ever calling `rng.random()`. A 2-or-3-option
    species consumes exactly one roll and walks its options via
    cumulative percentage thresholds in the source's own listed order.
    Returns `None` only for `Monster.NOMONSTER` (no distribution
    recorded).
  - ~~Deliberately not wired anywhere~~ **wired into `turn/
    world_generation.py _create_feature()` as of Phase 246**, once that
    module's own Phase 242 existence closed this phase's own "nothing
    to wire it to yet" gap -- see Phase 246's own note below.
  - 12 new tests in `tests/test_monster.py`: full-coverage/sentinel-
    exclusion/100%-sum checks across all 60 species, single/two/three-
    option data samples, `roll_monster_alignment()`'s no-roll behavior
    for single-option species, both sides of a two-option threshold,
    all three segments of a three-option cumulative walk, and
    confirmation that exactly one roll is ever consumed. Full suite:
    2239 passed (2227 unchanged + 12 new).
- **Phase 177**: closes `Desktop/MOSTRI con statistiche.txt`'s
  Magic Abilities column ("1 NE", "3 WH, 3 PS, 3 EL, 2 IL") for the 29
  of 60 real monster species that have one. Authorized directly by the
  user: "altro gap da riempire sempre che riguarda i mostri: Conteggio
  delle Abilità Magiche per scuola" ("another gap to fill, also about
  monsters: count of Magic Abilities by school").
  - `models/monster.py`: new `MONSTER_MAGIC_ABILITIES: dict[Monster,
    dict[Ability, int]]`. The source's own `WH`/`NE`/`EL`/`PS`/`IL`
    abbreviations map onto `models/enums.py Ability`'s 5 magic-school
    members (`WHITE`/`NECROMANCY`/`ELEMENTAL`/`PSYCHIC`/`ILLUSION`) --
    cross-checked directly against `Monster.WHITE_MAGE`/`NEC_MAGE`/
    `ELE_MAGE`/`PSY_MAGE`/`ILL_MAGE`'s own species names, which name
    their own primary school and use exactly these abbreviations for
    it (e.g. Renegade Priest/`WHITE_MAGE` reads "3 WH, 2 NE, 2 IL").
  - **Unlike Alignment, this is a fixed fact per species, not a
    weighted roll** -- no new roll function needed. Only 29 of 60
    species appear in the dict; the other 31 genuinely have no magic
    abilities in the source (absent, not a hidden zero-everything row,
    the same convention `MONSTER_STATS`'s own 6-of-60 coverage already
    established).
  - ~~Deliberately not wired anywhere~~ **wired into `turn/
    search_execution.py` as of Phase 209**, once that phase built the
    CAST orchestration engine for Search encounters -- see that
    phase's own note above.
  - 7 new tests in `tests/test_monster.py`: exact 29-species coverage
    (with a subset of the blank-column species confirmed absent),
    single-school and four-school data samples, a cross-check against
    the five Renegade-mage species' own school-matching names, and a
    positive-levels sanity sweep. Full suite: 2246 passed (2239
    unchanged + 7 new).
- **Phase 178**: guardian-monster Special Encounter Plans,
  plus two confirmed corrections to how an Encounter Plan's tactic list
  resolves. `Desktop/Piani speciali d'incontro dei mostri.txt` (supplied
  2026-07-16) gives all 60 real monster species their own percentage-
  weighted plan (rolled on a d100), with 4 species (Gold Dragon, Titan,
  Renegade Necromancer, Witch) getting one further variant used
  unconditionally when the attacking hero/King is Undead-aligned.
  Preceded by the user's own direct confirmation of the general
  default-behavior rule, quoted in full in both new modules' own
  docstrings: "Quando finiscono le azioni che vengono messe nel piano
  d'incontro il personaggio inizia a usare automaticamente il comando
  ME ... Il personaggio di default continua a usare il comando ME a
  mischia finche' muore lui o il mostro."
  - `models/enums.py`: new `SPELL_ABBREVIATION`/`SPELL_BY_ABBREVIATION`
    (35 real spells, sourced verbatim from `CTBOTH.PAS`'s own `spab`
    table) decode the source's own `CA-XX` Cast notation (e.g. `CA-HA`
    = `Spell.HAND_OF_DEATH`) -- every one of the 11 tokens this source
    uses resolves to one of the 10 "Personal-Combat-only" spells
    `cast_execution.py`'s own docstring already names as unmodeled, or
    to `Charm`, confirming this really is the personal-combat spell set.
  - `models/monster_encounter_plan.py` (new): `MONSTER_ENCOUNTER_PLANS`
    (all 60 species) and `roll_monster_encounter_plan()`. "ME fino alla
    fine" is modeled as one plain trailing `Maneuver.MELEE` tactic --
    `resolve_melee_duel()` already fights an entire Melee tactic to the
    death in one call, so no special "repeat forever" marker is needed.
    A single-variant species (or the Undead override) never consumes a
    roll, the same no-roll convention Phase 176's `roll_monster_
    alignment()` established. **Per the user's own explicit decision**,
    a rolled `CAST` entry stays completely inert data this phase -- no
    personal-combat spell-effect engine exists for any of these 11
    spells yet, so it's skipped by the tactic walk exactly like a
    player's own unwired `CAST` tactic always has been.
  - `turn/search_execution.py` -- two corrections, both confirmed by the
    user before the plan data was even supplied:
    - **The guardian now gets its own Fire Arrow phase independent of
      the leader's plan.** `execute_search()` rolls the guardian's own
      plan (using `leader.alignment is Alignment.UNDEAD` for the
      override condition) purely to check whether it contains a bare
      `SHOOT` -- if so, Fire Arrow resolves even when the leader's own
      submitted plan never lists `SHOOT` at all (species like Titan or
      Red Dragon previously never got to use their signature ranged
      attack unless the human player happened to also write `FI`).
      Still resolves through the same single, symmetric
      `resolve_fire_arrow_duel()` call, so the already-confirmed "only
      one FI order per encounter" rule (Phase 173) still holds.
    - **An exhausted tactic list now defaults to Melee instead of
      reporting "inconclusive."** Previously, a plan whose Fire Arrow
      tactic ran dry with nobody dead and no further tactic afterward
      fell through to a `winner=None` fallback -- contradicting the
      user's own confirmed default. The fallback now resolves one full
      `resolve_melee_duel()` call instead. One pre-existing test
      (`test_execute_search_shoot_exhausted_with_no_further_tactic_*`)
      updated for this now-corrected behavior, the same "fix the
      test to match the newly-confirmed real behavior" pattern Phase
      170's own Flee-ordering correction already used.
  - 25 new tests: `tests/test_spell_name.py` (+4, abbreviation table
    coverage/inversion), `tests/test_monster_encounter_plan.py` (new,
    19 tests -- full coverage, 100%-sum checks, the "ME fino alla fine"
    trailing-tactic convention, Dryad's 5-discrete-round preservation,
    Titan's 10-variant spread, the Undead-override bypass, threshold
    boundaries), `tests/test_search_execution.py` (+5 -- guardian-wants-
    Shoot firing independently of the leader's plan, no double
    resolution when both sides want Shoot, the leader's own Undead
    alignment threading into the guardian's own roll). Full suite: 2271
    passed (2246 unchanged + 25 new).
- **Phase 179**: the three combat ranges, and the spell-
  disruption formula. Authorized directly by the user ("progetta e
  implementa, poi nelle prossime sessioni ti illustrero' gli
  incantesimi" -- "design and implement, then in future sessions I'll
  walk you through the spells"), following a real worked-example combat
  log and two rulebook/mechanic quotes the user supplied directly.
  - `turn/encounter.py`: new `CombatRange` enum (`SPELL_RANGE`,
    `BOW_RANGE`, `MELEE_RANGE`, ordered farthest-to-closest), sourced
    from rulebook [5.0] quoted in full: "Ci sono tre distanze nel
    combattimento: portata d'incantesimo, portata d'arco e zona di
    mischia. La prima e' la distanza maggiore e consente solo l'uso di
    incantesimi o attacchi con armi da lancio. In zona di mischia solo
    incantesimi o attacchi corpo a corpo (quest'ultimi avranno comunque
    sempre la precedenza). Gli Incontri solitamente iniziano a portata
    di incantesimo." Matches both the confirmed default starting range
    and a real worked example's own progression ("closed to bow range"
    / "charged into melee range", each its own narrated beat).
  - New `spell_disruption_chance(hits_taken_this_round) -> float` and
    `resolve_spell_disruption(hits_taken_this_round, rng) -> bool`,
    sourced from the user's own confirmed formula: "questo succede
    quando si subiscono dei danni prima di provare a lanciare un
    incantesimo. Ogni danno da' il 20% comulativo (95% massimo) di non
    riuscire a lanciare l'incantesimo perdendo il round di
    combattimento." Counts hits landed, not damage points; a caster
    who took zero hits this round never consumes a roll (always
    succeeds), the same no-roll convention Phase 176's `roll_monster_
    alignment()` established.
  - **Deliberately not wired any further, by the user's own explicit
    scoping**: neither primitive is threaded into `turn/
    search_execution.py`'s own tactic walk yet -- a real `CAST` tactic
    still needs to know what each of the 10 Personal-Combat-only spells
    actually does before disruption has anything to disrupt. Both are
    modeled now as clean, independently-testable primitives, the same
    "confirmed mechanic modeled before its consuming pipeline exists"
    pattern Phase 176/178 already established.
  - 6 new tests in `tests/test_encounter.py`: `CombatRange` ordering,
    the disruption formula's per-hit scaling and 95% cap, the zero-hits
    no-roll case, the worked example's own exact 1-hit/20% boundary,
    and single-roll consumption. Full suite: 2277 passed (2271
    unchanged + 6 new).
- **Phase 180**: Holy Symbol [HO], the first of an unknown-
  length series of individual Personal-Combat spell effects the user
  is walking through "nelle prossime sessioni" (across future
  sessions), project-original (user-supplied, project author). Quoted
  in full: "Holy Symbol [HO] (Incantesimo di Combattimento
  Individuale): il Simbolo Sacro serve ad invocare la protezione
  divina e riduce le probabilita' dell'avversario di colpire nel tiro
  con l'arco e nel corpo a corpo del 10% per livello di abilita'. Ad
  esempio, se un giocatore che e' al livello 1 combatte contro un
  avversario che ha la probabilita' base di colpire pari al 50%, la
  ridurra' del 5% (il 10% del 50% equivale al 5%). Se usato contro un
  personaggio o un mostro Non-Morto, come un vampiro o un fantasma,
  oppure contro un mostro anti-holy come un demone, questo incantesimo
  riduce la probabilita' di colpire del 20% per livello di abilita' e
  infligge 1-4 punti ferita di danno per livello di abilita'."
  - `turn/encounter.py`: new `holy_symbol_hit_chance(base_hit_chance,
    skill_level, *, target_is_undead_or_anti_holy=False) -> float`,
    applying the reduction as a multiplier on the opponent's own base
    hit chance (`base_hit_chance * (1 - rate * skill_level)`, matching
    the worked example exactly: level 1 vs. a 50% base -> 45%), floored
    at 0% as an engineering safeguard, not a guessed game-balance rule.
    `rate` is `HOLY_SYMBOL_HIT_CHANCE_REDUCTION_PER_LEVEL` (0.10)
    normally, or `HOLY_SYMBOL_UNDEAD_HIT_CHANCE_REDUCTION_PER_LEVEL`
    (0.20) against an Undead or Anti-Holy target.
  - New `roll_holy_symbol_undead_damage(skill_level, rng) -> int`: one
    independent 1-4 die (`HOLY_SYMBOL_UNDEAD_DAMAGE_RANGE_PER_LEVEL`)
    per skill level, summed -- **confirmed directly by the user** via
    `AskUserQuestion`, since "1-4 punti ferita di danno per livello di
    abilita'" was genuinely ambiguous between several real conventions
    (a single roll scaled by level, a single roll multiplied by level,
    or one independent roll per level summed). Level 2 rolls two
    separate 1-4 dice and adds them (range 2-8). `skill_level` 0
    returns 0 without consuming a roll, the same no-roll-when-the-
    outcome-is-fixed convention `resolve_spell_disruption()` (Phase
    179) already established.
  - **Who counts as "Undead or Anti-Holy" is left to the caller**, not
    computed inside these functions: `models/alignment.py Alignment.
    ANTI_HOLY` already covers exactly this category in this project's
    own data (`models/monster.py MONSTER_ALIGNMENT_DISTRIBUTION`,
    Phase 176 -- every species the source names as an example, Ghost/
    Vampire/Banshee/Mummy/Lich/Spectre and every demon, Balrog/
    Marilith/Succubus/Rakshasha/Ice_Devil/Bone_Devil/Imp, is a 100%-
    `ANTI_HOLY` species there), so a future wiring phase can pass
    `target.alignment is Alignment.ANTI_HOLY` directly -- these pure
    functions just take a `target_is_undead_or_anti_holy: bool` flag
    rather than reaching into `GameState` themselves.
  - **Not wired into `turn/search_execution.py`'s combat resolution
    this phase either**, for the same reason as Phase 179's own
    primitives: this is the first of an unknown-sized set of Personal-
    Combat spells still to come, and wiring a real `CAST`-tactic combat
    engine before more of that set is known would mean redesigning it
    repeatedly as each new spell arrives.
  - 8 new tests in `tests/test_encounter.py`: the worked-example hit-
    chance case (level 1 vs. 50% -> 45%), per-level scaling, the
    Undead/Anti-Holy 20%-per-level variant, a 0%-floor edge case at a
    high skill level, the level-0 no-roll case, the damage-roll's 1-4
    range at level 1, the confirmed one-roll-per-level-summed
    convention (verified by counting the underlying `random()` draws,
    not just checking the output range), and the damage range constant
    itself. Full suite: 2285 passed (2277 unchanged + 8 new).
- **Phase 181**: two confirmed facts about Holy Symbol,
  supplied directly by the user: it's tied to `Ability.WHITE` (White
  Magic, the WH talent), and -- "come tutti quelli di combattimento" --
  every individual Personal-Combat spell effect caps its own skill-
  level scaling at level 4. Quoted in full: "E' un incantesimo legato
  al talento magia bianca (WH). Comunque questo incantesimo, come tutti
  quelli di combattimento ha il CAP al livello 4. Quindi se ha il
  talento WH a 5 questo incantesimo -- come tutti -- ha gli stessi
  effetti del livello 4."
  - `turn/encounter.py`: new `PERSONAL_COMBAT_SPELL_LEVEL_CAP = 4`,
    documented as covering *all* Personal-Combat spells, not just Holy
    Symbol -- future spells in this same family should apply the same
    cap. `holy_symbol_hit_chance()` and `roll_holy_symbol_undead_
    damage()` both now clamp their own `skill_level` input to this cap
    internally (`min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)`)
    before using it, so a WH-5-or-higher caster gets exactly the WH-4
    result/dice count.
  - One pre-existing Phase 180 test (`test_holy_symbol_hit_chance_
    floors_at_zero_instead_of_going_negative`) no longer held once the
    cap capped the maximum possible reduction at 80% (4 levels x 20%) --
    a positive base chance can no longer be driven all the way to zero
    through skill-level scaling alone. Replaced with two tests: the cap
    itself (`test_holy_symbol_hit_chance_caps_skill_level_at_4`, WH 5
    and WH 100 both matching WH 4 exactly) and a renamed nonnegative-
    floor check at the capped maximum reduction. The floor safeguard's
    `max(0.0, ...)` code itself is untouched -- it's no longer reachable
    through the public functions' own inputs, but stays as a cheap
    defensive clamp.
  - 3 new/changed tests in `tests/test_encounter.py`: the hit-chance cap
    (WH 5 and WH 100 == WH 4), the renamed nonnegative-floor-at-the-cap
    check, and the damage-roll cap (WH 5 rolls exactly 4 dice, verified
    by counting `random()` draws). Full suite: 2287 passed (2285 base -
    1 replaced + 3 new).
- **Phase 182**: Spiritwrack [SP], the second White Magic
  (WH) Personal-Combat spell effect, project-original (user-supplied).
  Quoted in full: "Spiritwrack [SP] (Incantesimo di Combattimento
  Individuale): chi lancia l'incantesimo pronuncia parole sacre che
  provocano nell'avversario violenti spasimi che lo indeboliscono
  nello spirito e nel corpo. La vittima non puo' lanciare incantesimi
  ne' tirare con l'arco e il danno che procura nel corpo a corpo e'
  ridotto di 1/2 punto danno per livello di abilita' di chi lancia
  l'incantesimo, arrotondato casualmente per eccesso o per difetto.
  Questo incantesimo e' inefficace contro mostri Non-Morti (questi
  sono: Spectre, Ghost, Vampire, Mummy, Banshee, Lich) o meccanici (che
  non hanno anima, questi sono: Golem, Gargoyle) e i suoi effetti sono
  dimezzati contro mostri di intelligenza animale [Gryphon,
  Elasmosaurus, Giant Worm, Giant Wolverine, Giant Amoeba, Giant
  Praying Mantis, Giant Scorpion, Giant Wasp, Giant Spider, Giant
  Octopus, Giant Clam, Great White Whale]." Same WH talent link and
  level-4 cap as Holy Symbol (Phase 181).
  - `models/monster.py`: new `SPIRITWRACK_UNDEAD_MONSTERS` (Spectre,
    Ghost, Vampire, Mummy, Banshee, Lich), `SPIRITWRACK_MECHANICAL_
    MONSTERS` (Golem, Gargoyle), and `SPIRITWRACK_ANIMAL_INTELLIGENCE_
    MONSTERS` (the 12-species list above) -- confirmed, by direct grep
    before adding, to be a genuinely separate classification axis from
    `Alignment.UNDEAD`/`Alignment.MECHANICAL` (neither is actually used
    anywhere in `MONSTER_ALIGNMENT_DISTRIBUTION`; e.g. the six Undead
    species there are all 100%-`Alignment.ANTI_HOLY`, from the outlook/
    kingdom-alignment axis, not this one). Kept as three separate sets
    (Undead and Mechanical stay apart even though both produce the same
    "ineffective" outcome) since a future spell might care about only
    one of the two reasons.
  - `turn/encounter.py`: new `spiritwrack_blocks_cast_and_archery(*,
    target_is_immune=False)` (True unless the target is Undead or
    Mechanical) and `spiritwrack_melee_damage_reduction(skill_level,
    rng, *, target_is_immune=False, target_is_animal_intelligence=
    False)` -- 1/2 point per level, randomly rounded up or down when
    the exact value isn't whole (e.g. level 1's own 0.5 rounds up half
    the time), 0 without a roll if immune, halved to 1/4 point per
    level if Animal-Intelligence. Both cap `skill_level` at
    `PERSONAL_COMBAT_SPELL_LEVEL_CAP` (Phase 181), same as Holy Symbol.
  - **The "halved effects against Animal-Intelligence" ambiguity**
    (a binary spell-block can't literally be halved) **resolved
    directly with the user via `AskUserQuestion`**: only the numeric
    Melee damage reduction is halved; `spiritwrack_blocks_cast_and_
    archery()` doesn't take an Animal-Intelligence flag at all and
    always applies at full strength unless the target is immune --
    in practice mostly moot, since none of the twelve Animal-
    Intelligence species actually cast spells or shoot bows.
  - **Not wired into `turn/search_execution.py`'s combat resolution
    this phase either**, same reason as Holy Symbol (Phase 180): more
    Personal-Combat spells are still to come across future sessions.
  - 15 new tests: `tests/test_monster.py` (+4 -- the three species
    lists match the user's own lists exactly, and are pairwise
    disjoint), `tests/test_encounter.py` (+11 -- the cast/archery block
    default and immune bypass, the immune-target zero-no-roll case
    (including when also flagged Animal-Intelligence), the level-0
    case, the whole-number no-roll case at level 2, the random-rounding
    behavior at levels 1 and 3, the level-4 cap (including levels 5 and
    100 matching it exactly), the Animal-Intelligence halved-rate
    rounding, the halved rate's own no-roll case at the capped level,
    and the rate constants themselves). Full suite: 2302 passed (2287
    unchanged + 15 new).
- **Phase 183**: Charm [CH], tied to `Ability.PSYCHIC` (PS)
  normally. Charm is the first spell confirmed to have *both* an
  Action-Cast form (already implemented, Phase 29) and a Personal-
  Combat form -- unlike every Personal-Combat spell covered so far
  (Holy Symbol, Spiritwrack), which are Personal-Combat-*only*. Real
  `models/monster_encounter_plan.py` data already used `CA-CH` (the
  Dryad's own encounter plan, Phase 178) before this dual nature was
  explicitly confirmed. Quoted in full: "Charm [CH] (Incantesimo
  d'Azione o di Combattimento Individuale): se lanciato su un Eroe che
  si trova nella stessa provincia e che non comanda unita' militari
  permette a chi lo usa di assoldare l'Eroe gratuitamente (fatti salvi
  i costi di mantenimento che vanno comunque pagati). 'Altrimenti
  consente a chi lancia l'incantesimo di ingraziarsi il suo avversario
  e sfuggire incolume al combattimento'. Per i personaggi Non-Morti
  questo incantesimo appartiene alla magia Negromantica (e non alla
  magia Psichica). ... Praticamente se usato in combattimento equivale
  a un comando FL che riesce sempre con la dicitura: (eroe o mostro)
  incanta (eroe o mostro) e questo lo lascia andare via senza
  problemi."
  - `turn/encounter.py`: new `CHARM_FLEE_ALWAYS_SUCCEEDS = True` --
    the entire Personal-Combat mechanic. Unlike a normal Flee attempt
    (`turn/search_execution.py FLEE_CHANCE`, keyed by `MonsterSpeed`,
    never guaranteed), a Charm-as-Flee always succeeds, no roll, no
    skill-level-scaled magnitude at all (`PERSONAL_COMBAT_SPELL_
    LEVEL_CAP` doesn't apply here, unlike Holy Symbol/Spiritwrack). Not
    wired into `turn/search_execution.py`'s combat resolution this
    phase either, same reason as every other Personal-Combat spell;
    the narration itself belongs in `report/turn_report.py` alongside
    `render_flee_failure()` once a real CAST-tactic engine exists.
  - `turn/cast_execution.py _execute_charm` (Action-Cast form): two
    real fixes/additions this phase. (1) A co-located Hero must now
    command **no** armies to be a valid free-hire target -- the
    source's own "che non comanda unita' militari" condition was
    previously unchecked entirely; a Hero who commands armies is
    instead the Personal-Combat scenario the "Altrimenti" sentence
    describes, handled by `CHARM_FLEE_ALWAYS_SUCCEEDS` above, not this
    function. (2) New `_spell_ability()` helper: an Undead caster's
    Charm now draws on `Ability.NECROMANCY` instead of `Ability.
    PSYCHIC` for both the success roll and any future level-dependent
    magnitude -- `LeaderState.alignment` (Phase 162) already carries
    the data this needed, no new field required.
  - **The Undead-King "Seduzione" branch, confirmed but deliberately
    not modeled**: when an Undead King (not a Hero) casts Charm on a
    Hero purely as an Action Spell, it gradually turns the target
    Undead instead of hiring them -- alignment shifts 1-3 ordinal
    positions per successful cast (`models/alignment.py ALIGNMENT_
    ORDINAL`, Phase 162), with the target's own resistance growing
    with skill level even though the spell's base success chance isn't
    reduced. Left unimplemented: the resistance formula itself isn't
    specified precisely enough to model without guessing -- same
    category of gap as this file's own Resurrection King-Heir case.
  - 5 new tests: `tests/test_cast_execution.py` (+4 -- the new "target
    commands military units" rejection, the Undead-caster Necromancy
    override actually taking effect, that an Undead caster's own
    Psychic skill no longer counts, and that a non-Undead caster is
    unaffected), `tests/test_encounter.py` (+1 -- the guaranteed-Flee
    constant). Full suite: 2307 passed (2302 unchanged + 5 new).
- **Phase 184**: Psychic Blast [PS], tied to `Ability.
  PSYCHIC` (PS). Quoted in full: "Psychic Blast [PS] (Incantesimo di
  Combattimento Individuale): chi lancia l'incantesimo proietta una
  raffica di energia mentale con cui stordisce il nemico guadagnando
  da 2 a 5 round supplementari d'attacco." ("The caster projects a
  burst of mental energy that stuns the enemy, gaining 2 to 5 bonus
  attack rounds.") Unlike every spell modeled so far in this family,
  there's no skill-level scaling at all -- a flat roll regardless of
  the caster's own Psychic level, so `PERSONAL_COMBAT_SPELL_LEVEL_CAP`
  doesn't apply here either (same as Charm, Phase 183).
  - `turn/encounter.py`: new `PSYCHIC_BLAST_STUN_ROUNDS_RANGE = (2,
    5)` and `roll_psychic_blast_stun_rounds(rng)` -- one uniform roll,
    the entire mechanic. What a caller does with the returned round
    count (extra Melee swings? a stun status the opponent can't act
    during?) is left to a future tactic-walk engine, same "not wired
    into `turn/search_execution.py` yet" scoping as every other
    Personal-Combat spell.
  - 3 new tests in `tests/test_encounter.py`: the range constant, the
    roll staying within `[2, 5]` across the full probability spread,
    and exactly one roll consumed per call. Full suite: 2310 passed
    (2307 unchanged + 3 new).
- **Phase 185**: Telekinetic Storm [TE], tied to `Ability.
  PSYCHIC` (PS). Quoted in full: "Telekinetic Storm [TE] (Incantesimo
  di Combattimento Individuale): chi lancia l'incantesimo provoca una
  tempesta telecinetica, con epicentro vicino alla vittima, che
  solleva in aria piccoli oggetti e li fa ruotare vorticosamente in
  tutte le direzioni. L'incantesimo infligge da 4 a 16 punti danno
  alla vittima. Alcuni oggetti colpiscono anche chi lancia
  l'incantesimo: se egli si trova in zona di mischia, riceve da 4 a 16
  punti danno; da 2 a 8 se e' a portata d'arco e da 1 a 4 se e' a
  portata di incantesimo. La Tempesta Telecinetica e' inefficace
  contro i mostri sottomarini [Elasmosaurus, Giant Octopus, Giant
  Clam, Great White Whale, Mermaid]." No skill-level scaling at all,
  same as Charm/Psychic Blast.
  - `models/monster.py`: new `TELEKINETIC_STORM_SUBMARINE_MONSTERS` --
    a fourth, independent classification axis (same rationale as
    Phase 182's own three): not a re-reading of `Alignment` (Mermaid's
    own 50%-`GOOD`/50%-`DRUID` entry has nothing to do with being
    submarine), and only partially overlapping with `SPIRITWRACK_
    ANIMAL_INTELLIGENCE_MONSTERS` (four species are both animal-
    intelligence and submarine, two independent facts about them;
    Mermaid is submarine but not animal-intelligence, proving the
    lists are genuinely separate).
  - `turn/encounter.py`: new `TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE =
    (4, 16)` and `TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_
    RANGE` (keyed by this module's own `CombatRange`, Phase 179: melee
    4-16, bow 2-8, spell 1-4). `roll_telekinetic_storm_victim_damage()`
    and `roll_telekinetic_storm_caster_damage(caster_combat_range,
    rng)` both take a `target_is_immune: bool` flag; when immune
    (submarine), *both* the victim's damage and the caster's own self-
    damage are suppressed together -- the storm never manifests at
    all against them, unlike Spiritwrack's own immunity (Phase 182),
    which only ever affected the target's side.
  - 10 new tests: `tests/test_monster.py` (+2 -- the species list
    matches the user's own list exactly, and the confirmed partial
    overlap with `SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS`),
    `tests/test_encounter.py` (+8 -- both range constants, the victim
    damage roll staying in range, the immune-target zero-no-roll case
    for both victim and caster damage, and the caster damage roll at
    each of the three `CombatRange` values). Full suite: 2320 passed
    (2310 unchanged + 10 new).
- **Phase 186**: Invisibility [IN], tied to `Ability.
  ILLUSION` (IL). Quoted in full: "Invisibility [IN] (Incantesimo di
  Combattimento Individuale): la probabilita' di essere colpiti con
  l'arco o nel corpo a corpo viene dimezzata per la durata del
  combattimento. Usato nel Piano d'Incontro prima di rubare, questo
  incantesimo vale come un modificatore di +15% al tentativo di
  furto." Two independent effects, no skill-level scaling on either.
  - `turn/encounter.py`: new `INVISIBILITY_HIT_CHANCE_MULTIPLIER =
    0.5` and `invisibility_reduced_hit_chance(base_hit_chance)` --
    halves whatever base hit chance the opponent would otherwise have
    against the invisible combatant, applying equally to Fire Arrow's
    own hit-chance formula and the flat Melee hit chance. "Per la
    durata del combattimento" reads as a persistent status rather than
    a single-round effect, though no per-round status-tracking exists
    in this project yet to actually carry that duration.
  - New `INVISIBILITY_STEAL_ATTEMPT_BONUS = 0.15`: a flat +15
    percentage-point bonus to a Steal attempt's own success chance.
    **Confirmed to have no numeric formula to modify yet** -- a direct
    search found `turn/search_execution.py` already documents
    `Maneuver.STEAL` as decoded but entirely unwired, and the only
    other Steal-related code in this project is narrative-only
    (`report/turn_report.py render_take_gold()`/`render_steal_caught_
    and_ransomed()`/`render_ice_steal_blocked()`) or purely descriptive
    ability-tooltip text (`models/advanced_ability.py`'s own "the
    Thief adds 15% to his chance to Steal", never backed by code). This
    constant is recorded now, the same way Charm's own Undead-King
    "Seduzione" branch was (Phase 183) -- a confirmed, sourced fact
    ready for whichever future phase builds a real Steal-success
    formula.
  - 3 new tests in `tests/test_encounter.py`: the hit-chance multiplier
    constant, the halving applied to both a flat base chance and Fire
    Arrow's own formula, and the Steal-bonus constant itself. Full
    suite: 2323 passed (2320 unchanged + 3 new).
- **Phase 187**: Mirror-Image Phantasm (MI), tied to
  `Ability.ILLUSION` (IL) -- by far the most elaborate Personal-Combat
  spell covered so far, a genuine two-stage state machine rather than a
  single formula. Quoted in full (English, project-original,
  user-supplied): "The caster creates a mirror-image illusion of his
  opponent and sends the phantasm into combat... Before each combat
  round, there is a chance that the victim will disbelieve the
  illusion... 15% per level of the spellcaster (max 60%) is subtracted
  from the listed chance. Divine or Superhuman 120% / High Human 100%
  / Medium Human 80% / Low Human 60% / Animal 40% / Mechanical 20%...
  If the mirror image loses, the caster must continue the fight at the
  current combat range. If it wins, the real monster is mentally slain
  and falls to the ground. The illusion then turns on its master...
  The illusion must be disbelieved (at a bonus of 25% above Medium
  intelligence) or slain. If the illusion wins, ... the real monster
  revives and slays the fallen illusionist. If the illusion loses, the
  caster automatically finishes off the mentally-slain monster and
  claims the treasure."
  - `turn/encounter.py`: new `MirrorImageIntelligenceTier` enum (six
    tiers), `MIRROR_IMAGE_DISBELIEF_BASE_CHANCE` (the six listed
    percentages, several exceeding 100% before reduction),
    `MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL`/`_CAP` (15%/level, max
    60%), `mirror_image_disbelief_chance(base_chance, caster_skill_
    level)` (subtracts the reduction, clamped to [0%, 100%]), and
    `resolve_mirror_image_disbelief()` (the roll, no-roll-when-fixed
    convention at 0%/100%). New `MIRROR_IMAGE_MASTER_DISBELIEF_BONUS =
    0.25` and `MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE` (Medium
    Human's 80% + 25% = 105%) for Stage 2 -- **confirmed directly by
    the user via `AskUserQuestion`** that the same 15%/level reduction
    applies there too, since the source text doesn't restate it.
  - **Deliberately scoped to the two disbelief formulas only.** The
    full outcome tree (illusion-vs-opponent duel, then a second
    caster-vs-illusion duel if the illusion wins) is documented in full
    in the module docstring but not executed: both duels could reuse
    this module's own existing `Combatant`/`resolve_melee_duel()` (the
    illusion is explicitly a stat-copy of the opponent), but
    orchestrating the round-by-round disbelief-then-duel state machine
    is a new mini-engine this phase doesn't build, same "not wired into
    `turn/search_execution.py` yet" scoping as every Personal-Combat
    spell above. The "double dissipation" rule (a second Mirror-Image
    cast mid-fight cancels both illusions) is likewise documented only
    -- no numeric magnitude to model.
  - **Cross-referenced, not reused**: `MirrorImageIntelligenceTier.
    ANIMAL`/`.MECHANICAL` describe the same real-world categories
    `models/monster.py SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS`/
    `SPIRITWRACK_MECHANICAL_MONSTERS` (Phase 182) already enumerate by
    species, but the tier is taken as a caller-supplied enum value
    rather than looked up internally -- the other four tiers (Divine/
    Superhuman, High/Medium/Low Human) have no existing species
    classification in this project at all.
  - 8 new tests in `tests/test_encounter.py`: the base-chance table and
    the Stage-2 base-chance derivation, the per-level reduction, the
    60%-reduction cap, clamping at both 0% and 100%, and the no-roll
    convention at both ends plus a real in-between roll. Full suite:
    2331 passed (2323 unchanged + 8 new).
- **Phase 188**: Fireball [FI], tied to `Ability.ELEMENTAL`.
  Quoted in full: "Fireball [FI] (Incantesimo di Combattimento
  Individuale): se usato in un combattimento, provoca da 1 a 8 punti
  danno, più 1 punto danno per livello (max 4). Questo incantesimo è
  inefficace contro i mostri sottomarini." A single damage roll, no
  multi-stage mechanic.
  - `turn/encounter.py`: new `FIREBALL_DAMAGE_RANGE = (1, 8)` and
    `FIREBALL_DAMAGE_PER_LEVEL = 1`. `roll_fireball_damage(skill_level,
    rng, *, target_is_immune=False)` rolls the 1-8 range and adds
    `min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)` bonus damage --
    the user's own "max 4" phrasing matches the existing project-wide
    cap (Phase 181) exactly, so this phase reuses it rather than
    introducing a Fireball-specific cap constant. Returns 0 without a
    roll when `target_is_immune`.
  - **The `SUBMARINE_MONSTERS` rename.** Unlike Phase 185's Telekinetic
    Storm, which supplied its five submarine species explicitly, the
    user reused "mostri sottomarini" here without re-listing them --
    read together, this confirms both spells mean the exact same
    real-world category, not two coincidentally similar ones. So
    `models/monster.py`'s own `TELEKINETIC_STORM_SUBMARINE_MONSTERS` is
    renamed to `SUBMARINE_MONSTERS` in this phase (dropping the spell
    prefix), and both spells' `target_is_immune` flags are meant to be
    backed by this one shared set. This deliberately breaks the
    spell-prefixed convention Phase 182 established for Spiritwrack's
    three classification sets (kept prefixed there because Undead/
    Mechanical/Animal-Intelligence are three conceptually distinct
    reasons for the same outcome) -- here there is only one reason,
    shared by two spells. All cross-references (`turn/encounter.py`'s
    own Phase 185 docstring addendum, `tests/test_monster.py`'s import
    and assertions) were updated to the new name; the rename alone was
    confirmed non-breaking (2331 passed) before Fireball's own code was
    written.
  - 6 new tests in `tests/test_encounter.py`: the two range/per-level
    constants, the roll staying in range at level 0, the per-level
    bonus at a pinned roll, the level-4 cap being honored (level 5
    behaves identically to level 4), and the immune-target
    zero-no-roll case. Full suite: 2337 passed (2331 unchanged + 6
    new).
- **Phase 189**: Ice Suspension [IC], tied to `Ability.
  ELEMENTAL`. Quoted in full: "chi lo lancia rinchiude la sua vittima
  in un guscio magico di ghiaccio che lo blocca o lo rallenta per
  alcuni round. Può rimanere bloccato un mostro o un Eroe a cui restano
  fino a 4 punti ferita per livello di magia elementare di chi lancia
  l'incantesimo. (max 16)... il mago elementale si impossesserà di
  tutti gli oggetti magici che la vittima non porta con sé al momento
  e potrà scegliere tra fuggire (con successo automatico) o attendere
  che il ghiaccio si sciolga a sufficienza da permettere alla vittima
  di liberarsi. In questo caso guadagnerà 3 round supplementari
  d'attacco... Se l'incantesimo non blocca il bersaglio, quest'ultimo
  verrà rallentato. Il mago guadagnerà così da 1 a 3 round
  supplementari d'attacco, a seconda di quanta parte del corpo del
  mostro è racchiusa nel ghiaccio... Questo incantesimo è inefficace
  contro fantasmi, demoni e simili [Spectre, Genie, Balrog Demon,
  Marilith Demon, Succubus, Rakshasha, Ice Devil, Bone Devil, Imp,
  Ghost, Banshee]... e funziona in maniera differente contro mostri
  volanti [Vampire, Giant Wasp, Beholder, Green Dragon, Gold Dragon,
  Silver Dragon, Black Dragon, Red Dragon, Giant Eagle, Couatl, Roc,
  Gargoyle, Gryphon]. Contro questi provocherà da 5 a 10 punti danno
  (la creatura si schianta al suolo) e darà a chi ha lanciato
  l'incantesimo da 1 a 3 round supplementari d'attacco (indipendentemente
  dal livello nella magia)." By far the most branching Personal-Combat
  spell so far -- three mutually-exclusive outcomes selected by the
  target's own type, not by a single roll.
  - `models/monster.py`: new `ICE_SUSPENSION_IMMUNE_MONSTERS` (11
    species, partial-materiality creatures) and `ICE_SUSPENSION_FLYING_
    MONSTERS` (13 species) -- both kept spell-prefixed, unlike Phase
    188's `SUBMARINE_MONSTERS` unification, since no other spell in
    this project references "partial materiality" or "flying" yet.
    Confirmed mutually exclusive (no species in both).
  - `turn/encounter.py`: `ice_suspension_freeze_threshold(skill_level)`
    = `min(4 * skill_level, 16)`; `ice_suspension_is_frozen(victim_hp,
    skill_level)` checks whether the victim's remaining HP is at or
    below that threshold. If frozen: `ICE_SUSPENSION_SEIZES_UNCARRIED_
    MAGIC_ITEMS = True` (a confirmed fact with no consuming code yet --
    this project's item-ownership registry, Phase 140, has no "seize
    an item its holder isn't carrying" operation), and the caster picks
    between `ICE_SUSPENSION_FROZEN_FLEE_ALWAYS_SUCCEEDS = True` (same
    always-succeeds pattern as Charm's Flee, Phase 183) or waiting for
    `ICE_SUSPENSION_FROZEN_BONUS_ROUNDS = 3` (fixed, no roll). If not
    frozen ("rallentato"): `ice_suspension_slowed_bonus_rounds(
    victim_hp, skill_level)` = `floor(4 * threshold / victim_hp)`. For
    flying monsters: `roll_ice_suspension_flying_crash_damage()` (5-10)
    and `roll_ice_suspension_flying_bonus_rounds()` (1-3), both flat,
    no skill-level scaling.
  - **The slowed-bonus-rounds formula was reverse-engineered and
    confirmed via `AskUserQuestion`.** The user's own worked example
    (16 HP remaining, skill level 1 -> 1 bonus round, "16 diviso 4, fa
    ovviamente 1") is arithmetically inconsistent taken literally
    (16/4 = 4, not 1). `floor(4 * threshold / victim_hp)` with
    `threshold = min(4*1, 16) = 4` gives `floor(16/16) = 1`, reproducing
    the stated result exactly; the user confirmed this is the intended
    formula rather than a simpler level-only alternative also offered.
  - **Caller-side branch selection, not a `target_is_immune` flag.**
    Unlike Telekinetic Storm/Fireball (Phase 185/188), which each have
    one damage formula with a boolean suppress flag, Ice Suspension has
    three genuinely different formulas selected by monster type -- so
    the immune/flying checks are meant to happen in the future calling
    code (which function to call), not threaded through every
    function's own signature.
  - 15 new tests: `tests/test_monster.py` (+3 -- both species lists
    match the user's own lists exactly, plus mutual-exclusivity),
    `tests/test_encounter.py` (+12 -- the freeze threshold's level
    scaling and cap, the frozen/not-frozen boundary, all four
    frozen-branch constants, the slowed-bonus-rounds formula against
    the user's own example plus boundary cases, and both flying-branch
    roll ranges). Full suite: 2352 passed (2337 unchanged + 15 new).
- **Phase 190**: Hand of Death [HA], tied to `Ability.
  NECROMANCY` -- the first Necromancy Personal-Combat spell. Quoted in
  full: "chi lancia questo incantesimo fa ripetutamente il gesto di
  stringere forte il pugno... Chi sta usando la Mano della Morte non
  può lanciare altri incantesimi né attaccare a mischia e si difende
  nel combattimento a corpo a corpo al livello di abilità che ha in
  Necromancy e non a quello che ha in Melee. Ogni attacco sferrato da
  chi lancia l'incantesimo provoca 1 punto danno più ½ punto per
  livello in magia nera. La vittima non può lanciare incantesimi né
  tirare con l'arco e le sue probabilità di colpire nel combattimento
  corpo a corpo sono dimezzate. Quando chi lancia l'incantesimo viene
  colpito perde la concentrazione e l'incantesimo svanisce. La Mano
  della Morte è inefficace contro mostri meccanici [Gargoyle, Golem],
  Non-Morti [Spectre, Ghost, Vampire, Mummy, Banshee, Lich] o anti-holy
  [Balrog Demon, Marilith Demon, Succubus, Rakshasha, Ice Devil, Bone
  Devil, Imp]." ("Magia nera" = Necromancy in this project's own
  established terminology -- `models/office.py`'s own `Office.
  NECRO_MAGE: "Sorceror of Black Magic"` confirms the pairing.)
  - **No level cap** -- unlike Holy Symbol/Spiritwrack/Fireball, the
    user's own text states no maximum, so `roll_hand_of_death_damage()`
    applies `HAND_OF_DEATH_DAMAGE_PER_LEVEL = 0.5` uncapped, same
    treatment as Charm/Psychic Blast/Telekinetic Storm/Invisibility.
  - `turn/encounter.py`: the caster's own three self-imposed
    constraints while channeling are recorded as confirmed facts, not
    wired into any combat loop -- `HAND_OF_DEATH_BLOCKS_CASTER_OTHER_
    CASTS`/`HAND_OF_DEATH_BLOCKS_CASTER_MELEE_ATTACK = True`,
    `hand_of_death_caster_melee_defense_skill()` (an identity
    substitution documenting that the caster's own melee-defense
    initiative uses their Necromancy skill in place of Melee),
    `HAND_OF_DEATH_ENDS_WHEN_CASTER_IS_HIT = True`. The caster's own
    attack: `roll_hand_of_death_damage(skill_level, rng, *,
    target_is_immune=False)` -- `HAND_OF_DEATH_BASE_DAMAGE = 1` plus
    `HAND_OF_DEATH_DAMAGE_PER_LEVEL = 0.5` per level, using the same
    random-rounding-when-fractional convention Spiritwrack established
    (Phase 182). The victim's own halved hit chance:
    `hand_of_death_victim_hit_chance()` (`HAND_OF_DEATH_VICTIM_HIT_
    CHANCE_MULTIPLIER = 0.5`) -- **not** the same mechanic as
    Invisibility's own hit-chance halving (Phase 186), which halves
    the chance of *being* hit rather than the victim's own chance of
    *landing* a hit, so kept as its own spell-prefixed pair rather than
    merged.
  - **`spiritwrack_blocks_cast_and_archery()` renamed to
    `blocks_cast_and_archery()`.** Hand of Death's "non può lanciare
    incantesimi né tirare con l'arco" is the exact same restriction,
    word for word, as Spiritwrack's own victim effect (Phase 182) --
    confirmed as one shared game rule applied by two different spells,
    the same "same real category" test Phase 188 used for
    `SUBMARINE_MONSTERS`. All call sites and the one docstring
    cross-reference were updated; behavior unchanged.
  - `models/monster.py`: "mostri meccanici"/"Non-Morti" reuse
    `SPIRITWRACK_MECHANICAL_MONSTERS`/`SPIRITWRACK_UNDEAD_MONSTERS`
    directly (species-identical, same exception as `SUBMARINE_
    MONSTERS`). New `HAND_OF_DEATH_ANTI_HOLY_MONSTERS` (7 species) is
    a genuinely new set, kept spell-prefixed because it is a strict
    subset of Phase 189's own `ICE_SUSPENSION_IMMUNE_MONSTERS` (not
    identical -- that set also covers Spectre/Genie/Ghost/Banshee,
    which the user classifies as "Non-Morti" here instead).
    `HAND_OF_DEATH_IMMUNE_MONSTERS` is the union of all three.
  - **Single `target_is_immune` flag, not caller-side branch
    selection** -- unlike Ice Suspension (three different effects),
    Hand of Death has one effect uniformly suppressed when immune, so
    it follows Telekinetic Storm/Fireball's style instead.
  - 13 new tests: `tests/test_monster.py` (+3 -- the new anti-holy set,
    the three-way union, and the confirmed strict-subset relationship
    with Ice Suspension's own immune set), `tests/test_encounter.py`
    (+10 -- the three caster-constraint constants, the melee-defense
    substitution, both damage constants, the whole-vs-fractional
    rounding (including the no-roll case), the immune-target
    zero-no-roll case, the victim hit-chance halving and its immune
    carve-out, and the renamed `blocks_cast_and_archery()`'s own
    behavior). Full suite: 2365 passed (2352 unchanged + 13 new).
- **Phase 191**: Control Undead [CO], tied to `Ability.
  NECROMANCY` -- the second and final Necromancy Personal-Combat spell,
  completing the ten Personal-Combat-only spells `turn/cast_execution
  .py`'s own Phase 60 docstring already enumerated. Quoted in full:
  "chi lancia questo incantesimo può tenere sotto controllo qualunque
  mostro (ma anche eroe o RE) Non-Morto (Spectre, Ghost, Vampire,
  Mummy, Banshee, Lich) per il tempo necessario a piantargli un paletto
  nel cuore (o neutralizzarlo in un altro modo). Se però l'incantesimo
  fallisce, nella vittima designata si scatenerà una furia omicida che
  farà aumentare i suoi Punti Ferita del 50-100%."
  - **Targeting**: the same six species as `SPIRITWRACK_UNDEAD_
    MONSTERS` (Phase 182) -- reused directly, no new monster.py set
    needed this phase. "(ma anche eroe o RE)" confirms Undead-ness
    extends to characters too, recorded as a confirmed fact only;
    `LeaderState` has no "is this leader Undead" field to check yet.
  - **No success-chance formula is modeled.** The source text never
    gives one -- unlike every other numeric roll in this project, which
    always traces back to a quoted percentage or range. Reusing `turn/
    cast_execution.py`'s own `ACTION_SPELL_BASE_CHANCE`/`_CHANCE_PER_
    LEVEL` (rulebook [3.10]'s *general* Action-Cast success formula)
    would be exactly the kind of guess this project avoids: that
    formula is textually scoped to top-level Action-Cast spells, not
    the Personal-Combat-only spells [4.2x.4]-[4.2x.5] documents
    separately, and nothing confirms the two share a rate. So, the same
    way Ice Suspension left "flee or wait" to "a tactical decision for
    whatever future orchestration layer calls this" (Phase 189), this
    module models only the two branches' own confirmed magnitudes, not
    which branch is taken.
  - `turn/encounter.py`: **success** -- `CONTROL_UNDEAD_SUCCESS_
    NEUTRALIZES_TARGET = True`, a confirmed qualitative fact ("piantargli
    un paletto nel cuore"), no numeric magnitude, no consuming combat
    loop yet. **Failure** -- `CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE
    = (0.50, 1.00)` ("50-100%"); `roll_control_undead_failure_hp_
    increase(rng)` uses `rng.uniform()` rather than `rng.randint()` --
    the first continuous (non-integer-die) roll in this project, since
    a percentage isn't a die. `control_undead_failure_new_hit_points(
    hit_points, rng)` applies it: `round(hit_points * (1 + increase))`.
  - 6 new tests in `tests/test_encounter.py`: both constants, the roll
    staying within [0.50, 1.00], its single-roll consumption, and the
    new-hit-points calculation at both ends of the range. Full suite:
    2371 passed (2365 unchanged + 6 new).
- **Phase 192**: spell-cast success formula corrections. The
  user directly re-quoted Regolamento AK.txt [3.10] in full: "Un
  personaggio può lanciare un incantesimo solo se ha un livello di
  abilità di almeno 1 nel relativo Talento. La probabilità di riuscita
  di un Incantesimo d'Azione è del 15% più 15% per livello. Gli
  Incantesimi di Combattimento Individuale hanno una probabilità di
  riuscita del 30% più 15% per livello. Le probabilità di successo per
  incantesimi non possono mai superare il 95%. Se l'incantesimo
  fallisce non ci sono conseguenze dirette. Gli Incantesimi di
  Combattimento individuale funzionano esattamente nella maniera
  descritta e non hanno altre conseguenze di rilievo... I Reami
  Pagani... sono coadiuvati da un Ordine di Maghi. Tutti i personaggi
  appartenenti a quel Reame hanno quindi un modificatore +10% nei loro
  tentativi di lanciare qualsiasi incantesimo fuorché quelli di Magia
  Bianca." This confirmed two things this project had gotten wrong or
  left unconfirmed:
  - **`turn/cast_execution.py`'s own Action-Cast formula was uncapped**
    -- at skill level 6+ (15% + 15%*6 = 105%), `rng.random() < chance`
    was always true by accident (`random()` never reaches 1.0), not
    because of the confirmed 95% cap. New `ACTION_SPELL_CHANCE_CAP =
    0.95` fixes this for real -- a level-6+ caster now has a genuine 5%
    failure chance that didn't exist before. Confirmed non-breaking:
    no existing test relied on the old uncapped, always-succeeds
    behavior at high levels.
  - **Personal-Combat spells (Holy Symbol through Control Undead, all
    ten from Phases 180-191) have their own success formula after
    all** -- Control Undead's own Phase 191 addendum had explicitly
    declined to invent one, since none was quoted at the time. New
    `turn/encounter.py`: `PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE =
    0.30`, `PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL = 0.15`,
    `PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP = 0.95` (the same 95%
    ceiling, kept as its own citation-backed constant rather than a
    cross-import from `cast_execution.py`, since the two modules serve
    different tactic layers). `personal_combat_spell_cast_chance(
    skill_level, *, caster_is_pagan=False)` and `resolve_personal_
    combat_spell_cast(skill_level, rng, *, caster_is_pagan=False)`
    apply uniformly to all ten spells -- none needed a per-spell
    formula individually, since this is the one shared roll gating
    whether any of their already-modeled effects apply at all.
  - **Pagan Kingdoms' Ordine di Maghi**: `PAGAN_MAGE_ORDER_BONUS =
    0.10` (`cast_execution.py`) / `PERSONAL_COMBAT_PAGAN_MAGE_ORDER_
    BONUS = 0.10` (`encounter.py`), +10% to every spell-cast attempt
    except White Magic. `cast_execution.py`'s own `_roll_cast_success()`
    now takes `state: GameState` as its first parameter (all 13 call
    sites already had `state` in scope) and looks up the caster's own
    kingdom alignment via a new `_caster_kingdom_is_pagan()` helper --
    the same "look up `KingdomState.alignment`" pattern `turn/
    encounter.py`'s own `NEUTRAL_DUELIST_BONUS` (Neutral Kingdoms'
    Order of Duelists, [5.0]) already established, just for
    spellcasting instead of Melee/Archery. `encounter.py`'s own
    Personal-Combat version instead takes `caster_is_pagan` as a
    caller-supplied bool (the usual "pure function, boolean-flag, not
    internal lookup" pattern every spell above uses) -- the caller must
    pass `False` for White Magic spells (Holy Symbol, Spiritwrack)
    regardless of the caster's own kingdom.
  - **Also confirmed, not modeled**: the same quoted text describes
    per-turn Action-Cast quotas (1/turn, 2 at skill level 3, 3 at
    level 4) and a per-encounter "not twice with the same
    Personal-Combat spell" limit -- documented as confirmed facts in
    both modules' own docstrings, not wired in, since no per-turn or
    per-encounter cast-count state exists anywhere in this project yet.
  - 12 new tests: `tests/test_encounter.py` (+7 -- the formula's level
    scaling, its 95% cap with and without the Pagan bonus, and the
    resolve roll's success/failure), `tests/test_cast_execution.py`
    (+5 -- the Action-Cast cap being enforced for real at high skill
    level, the Pagan bonus applying to a non-White spell, the same
    roll failing without it, and the bonus being excluded for a White
    Magic spell). Full suite: 2383 passed (2371 unchanged + 12 new).
- **Phase 193**: Clairvoyance [4.22.3] and Hide_Feature
  [4.23.3] execution, closing 2 of the 12 previously-unexecuted spells
  (10 remain -- the Personal-Combat-only ten). The user asked directly
  which spells were still missing; both turned out to have stale or
  imprecise blocker claims in `cast_execution.py`'s own Phase-60 module
  docstring:
  - **Hide_Feature's "unpopulated `Feature` stub" blocker was already
    resolved back in Phase 75** (`models/feature.py`'s real model +
    `GameState.features`/`features_at(coord)`), just never revisited.
    [4.23.3] maps to `Ability.ILLUSION` (cross-referenced against
    `Illus_Terrain`/`Illus_Armies`'s existing entries, same [4.23]
    rulebook block). Since `CastRequest.target` for Hide_Feature only
    ever decodes to a province coordinate -- never a specific
    feature-instance id, confirmed against all 108 real sample Cast
    phases -- and [3.2] itself says a province can hold more than one
    feature, `_execute_hide_feature` hides **every** `Feature` at the
    resolved coordinate via the new `Feature.magically_hidden: bool =
    False` field. This is a deliberate, unsourced judgment call
    (documented on the function and in the module docstring's own
    "Phase 193 addendum"), not a guess at a disambiguation mechanism
    this project has no data to build. An empty-features province
    fails with `"no feature to hide"` before any success roll, the
    same "check applicability first" order every province-targeted
    spell here already uses. No consuming Explore/Search
    discovery-roll reads the new flag yet.
  - **Clairvoyance's blocker is real, but its citation wasn't**: the
    old docstring attributed the "per-character event feed" framing to
    `report/prose.py`'s own Phase 58 docstring, but a direct read
    confirms the phrase "story event" never appears there -- it
    originated and stayed local to `cast_execution.py` itself. [4.22.3]
    maps to `Ability.PSYCHIC` (cross-referenced against `Charm`/
    `Oratory`'s existing [4.22]-block entries). Only the confirmed half
    of the rulebook sentence ("for the rest of the turn, the caster
    knows everything that happens to the target") is modeled: a new
    `LeaderState.clairvoyance_watchers: set[int] = field(default_factory=
    set)` records which kingdom(s) currently watch a leader; a
    successful cast adds the caster's own `kingdom_id`. No event feed
    exists yet to actually surface anything to a watcher -- the same
    "model the confirmed effect, defer the consuming system" pattern
    this project has used for dozens of other spells/mechanics. No
    co-location/adjacency precondition either -- the sourced text names
    none, unlike `Kill_Enemy`'s own spell-specific "not co-located"
    check.
  - `report/turn_report.py`'s `render_cast_announcement()` gained
    `Spell.CLAIRVOYANCE` in `_CAST_ANNOUNCEMENT_TARGET_SPELLS` (reuses
    the existing `[`/`[1` character-name marker) and a brand-new `&`
    (Feature name) marker for `Spell.HIDE_FEATURE` -- the first spell
    whose own `SPELL_CAST_ANNOUNCEMENT` entry needs it, plus
    `Spell.HIDE_FEATURE` added to `_CAST_ANNOUNCEMENT_PROVINCE_SPELLS`
    for its `@` (province name) marker. Both `render_cast_announcement()`
    and `describe_cast()` gained a new `feature_name` parameter. Wand
    casting (`turn/use_mi_execution.py`) and the decode layer
    (`turn/cast_decode.py`) needed zero changes -- both were already
    spell-agnostic and fully ready for these two.
  - Corrected `cast_execution.py`'s own module docstring rather than
    silently rewriting it: the stale Hide_Feature/Clairvoyance
    "still unexecuted" bullets stay in place as the historical record
    of what blocked them through Phase 192, with a new "Phase 193
    addendum" section spelling out exactly what changed and why -- the
    same "correct via addendum, don't rewrite history" convention
    Phase 190-192's own docstring corrections already established.
  - Updated two pre-existing tests that had asserted Hide_Feature was
    unmodeled (`test_unmodeled_spells_report_a_reason_without_touching_
    state`, `test_dispatch_cast_hide_feature_is_not_executed`) to use
    `Spell.HOLY_SYMBOL` instead -- one of the ten still-genuinely-
    unmodeled Personal-Combat-only spells.
  - New tests: `tests/test_cast_execution.py` (+6 -- Clairvoyance's
    watcher-set success/missing-target/failed-roll cases, Hide_Feature's
    hide-every-feature/no-feature/unknown-province cases), `tests/
    test_turn_report.py` (+3 -- Clairvoyance's double-cast-clause
    announcement, Hide_Feature's feature+province announcement, and its
    missing-`feature_name` `ValueError` case), `tests/test_feature.py`
    (+1 -- `magically_hidden`'s explicit-True case, plus a default-value
    assertion added to the existing defaults test). Full suite: 2393
    passed (2383 unchanged + 10 new).
- **Phase 194**: Gate Angel -- the first of 10 "secret" spells
  (ordinals 25-34, outside the 25 documented `Spell` members) to get
  real execution, and the first spell text the user supplied directly
  rather than via Regolamento AK.txt. Quoted in full: '"GATE ANGEL"
  SPELL: Call Valhalla Hero... an extra-dimensional gate is opened to
  Valhalla, through which a hero of the same alignment as the
  spellcaster passes. The hero appears at the end of the current
  gameturn. Only one Valhalla hero can visit the world during a turn...
  Each alignment from Good to Evil can still be visited only once in
  each 5-turn period (for this spell, Divine kingdoms are treated as
  Good, and Undead as Evil). If more than one player casts the Gate
  Angel spell, one of the spells will be nullified. The spellcaster has
  no control over which hero arrives.' Already confirmed real and fully
  described by `models/advanced_ability.py`'s own
  `AdvancedAbility.GATE_ANGEL_SPELL` (White Magic pool, Phase 128) --
  the user's text matches that entry's `ADVANCED_ABILITY_DESCRIPTION`
  word for word.
  - `Spell.GATE_ANGEL: Ability.WHITE` added to `cast_execution.py`'s
    `_SPELL_ABILITY`; `Spell.GATE_ANGEL` added to `cast_decode.py`'s
    `NO_TARGET_SPELLS` (the rule text names no target field at all,
    matching Skeletal_Army's own precedent -- no real sample data
    exists to validate this against, since the secret-spell Trade->Cast
    rewrite this module's own docstring flags is "deliberately not
    handled" anywhere in this project).
  - Three new `GameState` fields model only the confirmed, sourced
    mechanics: `last_gate_angel_turn`/`last_gate_angel_kingdom` (the
    global once-per-turn Valhalla-visit lock -- unlike every other
    per-turn flag in this project, which is scoped to one leader/army/
    province) and `gate_angel_alignment_cooldown` (the per-alignment-
    group 5-turn cooldown, via new `_gate_angel_alignment_group()`
    folding `Alignment.DIVINE` into `GOOD` and `Alignment.UNDEAD` into
    `EVIL` -- the only two foldings the rule states; every other
    `Alignment` keeps its own bucket). `_execute_gate_angel` checks the
    global lock, then the alignment cooldown, then rolls -- the usual
    "check applicability first" order every spell here uses.
  - **No new `LeaderState` hero is synthesized.** This project has no
    character-generation system anywhere (name/race/skills/starting
    stats are all unsourced -- `models/game_state.py`'s own docstring
    already flags "populating a brand-new `GameState` from turn 0" as a
    distinct, larger, unsourced future task). Only the confirmed lock/
    cooldown state is modeled, the same "model the confirmed effect,
    defer the consuming/generating system" pattern as Clairvoyance's
    own `clairvoyance_watchers` (Phase 193).
  - "Only one hero per turn, one cast nullified" is modeled as strict
    first-come-first-served via this engine's own existing sequential
    per-leader phase dispatch (`turn_processor.py`'s `run_turn()`
    already processes each leader's Cast phase one at a time) --
    `last_gate_angel_turn` is checked before, and set immediately after,
    a successful roll, so any later Gate Angel cast the same turn fails
    outright before it even rolls. Which caster "wins" a same-turn tie
    is therefore whichever this engine's own dispatch order reaches
    first; the rulebook names no tie-breaking rule of its own to
    compare against, so no new end-of-turn batch-resolution machinery
    was needed or built.
  - "The spellcaster" reads as the acting Kingdom's own alignment
    (`state.kingdoms[kingdom_id].alignment`), the same "which Kingdom
    this cast concerns" convention `_execute_charm`'s own
    `target.kingdom_id = kingdom_id` write already establishes -- not
    `LeaderState.alignment`, which is frequently unrecorded (`None`)
    and this rule names no fallback for.
  - 7 new tests in `tests/test_cast_execution.py`: a successful cast
    setting both the global lock and the alignment cooldown, a second
    same-turn cast getting nullified, the alignment cooldown blocking a
    cast within 5 turns and allowing one at exactly 5, Divine/Undead
    each sharing the Good/Evil cooldown bucket, and a failed roll
    touching no state at all. Full suite: 2400 passed (2393 unchanged +
    7 new).
- **Phase 195**: corrects Gate Angel's Phase 194 mechanic with
  the real VALHALLA rules, which the user supplied in full in a
  follow-up message (quoted in the module docstring's own "Phase 195
  addendum"). Two Phase 194 design errors, both now fixed:
  - **The "per-alignment independent 5-turn cooldown" was wrong.** The
    real rule is a *rotating exclusion cycle* over exactly 5 alignments
    -- "Ciascun allineamento da Buono a Malvagio (quindi non Divine o
    Undead) riceverà una visita una volta ogni cinque turni." New
    `GATE_ANGEL_ELIGIBLE_ALIGNMENTS = (GOOD, DRUID, NEUTRAL, PAGAN,
    EVIL)` -- exactly the 5 `Alignment` members strictly between
    `DIVINE` and `UNDEAD` in `models/alignment.py`'s own
    `ALIGNMENT_ORDINAL` table. New `_gate_angel_due_alignment()` lazily
    picks (and caches per `turn_number`, via new `GameState.
    gate_angel_due_alignment`/`gate_angel_due_alignment_turn`) which
    alignment is due the first time any Gate Angel cast is attempted
    each turn, tracking already-used alignments in `GameState.
    gate_angel_cycle_visited` (cleared once all 5 are used) -- matching
    the user's own worked example turn-by-turn.
  - **Divine and Undead kingdoms never receive a visit at all** -- "I re
    Non-Morti e Divini possono entrare nel Vahlalla come Buoni o
    Malvagi, ma non ricevono visite dal Vahlalla" is unconditional,
    contradicting a literal reading of Gate Angel's own spell text
    ("Divine kingdoms are treated as Good, and Undead as Evil") as
    meaning they share the Good/Evil visit slot. That phrase instead
    describes which Valhalla roster a Divine/Undead King's *own* future
    legendary character joins if *they* personally achieve entry -- a
    fact about Valhalla's membership, not about who can receive a
    visit. Since `GATE_ANGEL_ELIGIBLE_ALIGNMENTS` never contains
    `DIVINE`/`UNDEAD`, this falls out automatically (their casts always
    fail with "not this alignment's turn for a Valhalla visit"), no
    special-case needed. `_gate_angel_alignment_group()` (the Phase 194
    folding helper) is removed.
  - **Tie-breaking is now genuinely random**, via reservoir sampling
    (new `_gate_angel_register_candidate()`): every due-alignment caster
    whose own roll succeeds is a candidate, and each new candidate
    replaces `GameState.last_gate_angel_kingdom`/`last_gate_angel_turn`
    with probability `1/N` (`N` = candidates seen so far this turn) --
    a single-pass algorithm giving a uniformly random winner among all
    of a turn's candidates, honoring "se c'è più di un giocatore in un
    allineamento, la scelta verrà fatta a caso" without needing new
    end-of-turn batch-resolution machinery (superseding Phase 194's
    "first-come-first-served" compromise). `CastExecutionResult.
    applied=True` now means "this cast's own roll succeeded and it
    entered the drawing," not necessarily "this kingdom's hero is the
    one that arrived" -- the authoritative fact is `last_gate_angel_
    kingdom` once the turn's whole dispatch completes, the same
    distinction this project's contested-province Move orders already
    draw.
  - **Confirmed but still out of scope**, cited in the module docstring
    for a future phase: the actual Valhalla hero roster (5 per-alignment
    files of named heroes, not yet supplied -- the user's own plan),
    the fixed leader id `#199` every visitor always gets, spawning
    "beside the King" (`is_king=True` among the winning kingdom's
    leaders), the visitor's fixed non-transferable magic item, the
    escalating per-visit action allowance (this project has no
    plan-authoring system to enforce it against), the one-Practice-
    phase-only limit, spell-immunity except Resurrection, army hand-off
    to the lowest-numbered leader (or adjacent garrison commander) on
    departure, and turn-deadline voiding.
  - Replaced all 7 of Phase 194's original Gate Angel tests in
    `tests/test_cast_execution.py` with 9 matching the corrected
    mechanic: matching/non-matching alignment, due-alignment caching
    across same-turn casts, Divine/Undead never matching, reservoir-
    sampling swap winning and losing, the 5-turn cycle resetting, and a
    failed roll touching no state. Full suite: 2402 passed (2393
    pre-Gate-Angel baseline + these 9).
- **Phase 196**: real Valhalla hero spawning, unblocked once
  the user supplied all 5 per-alignment roster files (`VALHALLA
  GOOD.txt`/`DRUID.txt`/`NEUTRAL.txt`/`PAGAN.txt`/`EVIL.txt`), 137
  named legendary heroes total. New `models/valhalla.py`
  `VALHALLA_ROSTER: dict[Alignment, tuple[ValhallaHero, ...]]`,
  transcribed via a one-off parser script (not hand-typed, to eliminate
  transcription risk across ~137 heroes x 32 numeric fields each) that
  reads the source files directly and cross-references every hero's
  own two skill/aptitude rows against `models/enums.py Ability`'s own
  declared order (`Ta Ma Na Ar Me Wh Ne El Ps Il Dr Th Ex Sp Sa`,
  confirmed to match exactly) and every `Oggetto:` item name against
  `models/treasure.py TREASURE_NAME`.
  - 61 of 63 distinct item names resolve directly (or via an obvious
    wording variant already present in this corpus). **"Feather of the
    Great Eagle" filled `MONSTER_AID_EAGLE`'s own confirmed
    `TREASURE_NAME` gap** (Phase 77's own docstring had flagged this as
    unfillable from `TREASURE.X2`) -- this project's first real name
    for that ordinal, sourced from VALHALLA data instead. Two items
    ("Horn of Neptune", "Hannibal's Grimoire", both on PAGAN heroes)
    match no `Treasure` ordinal at all, named or gap; left as
    `fixed_item=None` rather than guessed onto an unrelated slot --
    `fixed_item_name` still carries the raw text.
  - New `LeaderState.race: Race | None = None` -- the first field this
    project has ever needed for an individual leader's own race
    independent of their serving Kingdom's (`KingdomState.race`), since
    a Valhalla visitor keeps their own race regardless of which Kingdom
    they join.
  - New `turn/valhalla_execution.py finalize_gate_angel_visit(state,
    rng)`: once Gate Angel's own reservoir-sampling winner
    (`GameState.last_gate_angel_kingdom`/`last_gate_angel_turn`, Phase
    195) is final, picks a random hero from the winning turn's due-
    alignment roster and builds a real `LeaderState` -- fixed
    `leader_id=199` ("Il numero d'ordine del visitatore dal Vahlalla
    sara' sempre #199"), spawned beside the winning Kingdom's own King
    (`is_king=True`, falling back to the Kingdom's `home_province` if
    no King is on record -- an unsourced but reasonable fallback), with
    the hero's real skills/temper/alignment/race copied across, and the
    hero's own fixed magic item granted via `GameState.add_item()` --
    `models/treasure.py`'s own docstring already confirms this is the
    *only* real Pascal call site `Add_Tr` (the routine `add_item()`
    mirrors) is known to have: a narrow Valhalla-visitor special case,
    not a general item-generation pipeline. Skipped for the 2 heroes
    with `fixed_item=None`.
  - **Deliberately not wired into `turn/turn_processor.py`'s own
    `run_turn()` yet** -- `finalize_gate_angel_visit()` is a complete,
    independently testable function; the caller must invoke it exactly
    once per turn, after every leader's Cast phase has been dispatched
    (an earlier call risks picking the wrong kingdom, since a later
    same-turn candidate can still steal the reservoir-sampling win).
    Mirrors the exact "implement the execution function, wire it into
    the real dispatch loop in a later phase" split Phase 172/173
    already used for Cast execution itself.
  - **Still confirmed but out of scope**, cited in `turn/
    cast_execution.py`'s own "Phase 195 addendum" for whichever future
    phase builds turn-scoped visitor lifecycle tracking: the escalating
    per-visit action allowance, the one-Practice-phase-only limit,
    spell-immunity except Resurrection, the item's disappear-on-death
    rule, army hand-off on departure, and turn-deadline voiding.
  - 16 new tests: `tests/test_valhalla.py` (+8 -- roster coverage/
    counts, every hero's 30-value skill table, the `MONSTER_AID_EAGLE`
    fill, the 2 unresolved items, Divine/Undead heroes inside the
    Good/Evil buckets, Arthur's own Excalibur matching the rulebook's
    own example) and `tests/test_valhalla_execution.py` (+8 --
    no-visit/stale-turn no-ops, the fixed leader id, spawning beside
    the King, the home-province fallback, the item grant and its
    no-item case, and copying skills/temper/alignment/race).
    `tests/test_treasure.py` updated for the now-filled
    `MONSTER_AID_EAGLE` gap. Full suite: 2418 passed (2402 unchanged +
    16 new).
- **Phase 197**: closed `MONSTER_AID_WHALE`'s own
  `TREASURE_NAME` gap, the second of the two items Phase 196 had left
  unresolved. The user supplied its `TREASURE.X2`-equivalent row
  directly ("Horn of Neptune | Balene | Comando sulle Balene: la
  Tattica determina la resa; 33% di probabilita' di diserzione") --
  "Balene" (Whales) and the "33% di diserzione" figure match
  `MONSTER_COMMAND_ITEM`'s own confirmed "33% defections" formula
  exactly, and the name is independently corroborated by
  `models/valhalla.py`'s own Gelenor (PAGAN hero), who already carried
  this same item. `TREASURE_NAME` now has 95 entries (was 94);
  `BOOK_TACTICAL` is the sole remaining genuinely unfilled ordinal
  below 93. Updated `tests/test_treasure.py` (gap count, new verbatim
  sample) and `tests/test_valhalla.py`/`test_valhalla_execution.py`
  (Gelenor now resolves to a real item; the "no resolved item" test
  case moved to Xerxes, the one hero whose "Hannibal's Grimoire" still
  matches no ordinal at all). Full suite: 2419 passed (2418 unchanged +
  1 new).
- **Phase 198**: closed `BOOK_TACTICAL`'s own `TREASURE_NAME`
  gap, the last one below ordinal 93 -- and with it, the last of the
  63 distinct VALHALLA item names left unresolved. The user supplied
  its own description directly ("Hannibal's Grimoire se letto aumenta
  il talento Tattica (TA) di un livello"), matching `SKILL_BOOK`'s own
  confirmed "+1 Ability when read" mechanic and `TREASURE_LABEL`'s own
  "+1 Tactical when read" line for this exact ordinal; independently
  corroborated by `models/valhalla.py`'s own Xerxes (PAGAN hero), who
  already carried this same item. `TREASURE_NAME` now has 96 entries
  (was 95) -- only the three named uniques (94-96) remain genuinely
  unfilled anywhere in the catalog. Since no real VALHALLA hero has an
  unresolved `fixed_item` anymore, `test_valhalla_execution.py`'s
  "grants no item" test was rewritten to use a `monkeypatch`-fabricated
  `ValhallaHero` instead of a real roster entry, keeping
  `finalize_gate_angel_visit()`'s still-real `fixed_item is None`
  branch under test without asserting a false gap against real data.
  Full suite: 2420 passed (2419 unchanged + 1 new).
- **Phase 199**: wired `turn/valhalla_execution.py
  finalize_gate_angel_visit()` (Phase 196, deliberately left unwired at
  the time) into `turn/turn_processor.py run_turn()` -- the last open
  item the Gate Angel/Valhalla work had left. Called exactly once, after
  the `PHASE_LABELS` (P0-P4) loop completes, never inside it: a Gate
  Angel cast can succeed on any phase, and a later same-turn,
  same-due-alignment cast can still steal the reservoir-sampling win
  right up through the last phase (`turn/cast_execution.py`'s own
  "Phase 195 addendum"), so calling any earlier risks spawning the
  visitor for a kingdom a later phase's own cast displaces. When a
  visitor is spawned, one sentinel `PhaseDispatchResult` is appended
  (`segment_index=-1`, `phase_label="gate-angel-visit"`, `action=None`,
  `result` the new `LeaderState`) -- the same not-tied-to-a-real-plan-
  segment convention `_dispatch_contested_rebattles` already uses for
  `"forced-rebattle"`. No result is appended when no Gate Angel cast
  succeeded that turn. 3 new tests in `tests/test_turn_processor.py`:
  a full end-to-end cast-to-visitor-to-granted-item run (confirming the
  wiring reaches `GameState.items_held_by()`, not just the `LeaderState`
  shape), a mismatched-alignment cast producing no visit, and an empty
  turn producing no visit. Full suite: 2423 passed (2420 unchanged + 3
  new).
- **Phase 200**: modeled Words of Healing [WH]
  (`Spell.HEAL`), the eleventh Personal-Combat spell and the first of
  the ten secret-ordinal spells ([2.0]) to get a real mechanic --
  user-supplied: "New Special Combat Heal (can be casted using the
  command CA-WH)... The character is completely healed when the Words
  of Healing are spoken, gaining back all lost hit points. The spell
  is also half as likely to be disrupted by your opponent's tactics as
  other spells." Granted via `AdvancedAbility.WORDS_OF_HEALING_SPELL`
  (White Magic skill 5+, already fully documented at the model layer
  since an earlier phase) rather than the base-skill-1+ gate the other
  ten Personal-Combat spells use -- only the combat mechanic itself was
  missing.
  - `turn/encounter.py words_of_healing_heal(combatant,
    max_hit_points)` sets `Combatant.hit_points = max_hit_points`
    outright. `Combatant` has no separate "starting/max" hit-points
    field distinct from its current one (the same gap Troll
    regeneration's own Phase 155 addendum already flagged), so the
    caller supplies the combatant's own known max explicitly
    (`CHARACTER_HIT_POINTS` for a character, or a monster's own
    stat-block total) rather than a new field being invented.
  - `spell_disruption_chance()`/`resolve_spell_disruption()` gained an
    optional `chance_per_hit` keyword (default: the existing 20%
    constant, every prior caller unaffected); `words_of_healing_
    disruption_chance()`/`resolve_words_of_healing_disruption()` call
    through with half that rate, same 95% cap -- halving the per-hit
    rate rather than the final computed chance, so the cap still
    engages at the correct hit count.
  - No skill-level scaling on either effect (so
    `PERSONAL_COMBAT_SPELL_LEVEL_CAP` doesn't apply), matching
    Charm/Psychic Blast/Telekinetic Storm/Invisibility's own uncapped,
    non-scaling Personal-Combat effects.
  - `turn/cast_execution.py`'s own "the ten Personal-Combat-only
    spells" docstring note updated with a cross-reference to this
    eleventh one.
  - **Not wired into `turn/search_execution.py`'s combat resolution
    this phase either**, same reason as every other Personal-Combat
    spell in `turn/encounter.py`: no real `CAST`-tactic orchestration
    engine exists yet to call it from.
  - 11 new tests in `tests/test_encounter.py`. Full suite: 2434 passed
    (2423 unchanged + 11 new).
- **Phase 201**: modeled Scar Terrain [ST] (`Spell.SCAR_
  TERRAIN`), tied to `Ability.NECROMANCY` -- unlike every secret spell
  so far, an Action-Cast (province-targeted) spell, not a Personal-
  Combat one. User-supplied: "-2 Taxation, Change Race at 0... By the
  horrible power of this spell, a co-located or adjacent province is
  scarred and mangled, and its tax base is reduced by 2 gold
  immediately and permanently. When the tax base reaches 0 gold, the
  province becomes incapable of supporting normal life forms. If it's
  a land province, the racial type will change to Orcs, Dragons or
  Trolls (usually by immigration from an adjacent province) and the
  army type will change to something suitable to the new racial type.
  Sea provinces will just lose whatever provincial racial and army
  type they may have." Added to `turn/cast_decode.py
  PROVINCE_TARGET_SPELLS` (not `NO_TARGET_SPELLS` like Gate Angel,
  since this spell names a real province target).
  - `turn/cast_execution.py _execute_scar_terrain` increments the new
    `ProvinceState.scar_terrain_gold_reduction` field by
    `SCAR_TERRAIN_TAX_REDUCTION` (2) on every successful cast --
    cumulative and uncapped (an add, not a set, unlike Earthquake's
    own non-cumulative `tax_modifier_percent`). No terrain restriction,
    no skill-level scaling.
  - **"When the tax base reaches 0" is a real trigger this project
    genuinely cannot fire from real state yet** -- no revenue system
    anywhere tracks a province's own starting gold-value tax base to
    subtract from (the same gap `tax_modifier_percent`'s own docstring
    already flags). `scar_terrain_is_exhausted(remaining_tax_base)`
    models the check as a pure function (caller supplies the
    otherwise-unavailable remaining value, same pattern
    `turn/encounter.py`'s Ice Suspension uses for `victim_hit_points`)
    -- **not auto-invoked inside `_execute_scar_terrain`**.
  - `scar_terrain_collapse(province, new_land_race=None)` models the
    collapse effect itself, equally not auto-triggered. A Sea province
    unconditionally becomes `Race.NO_RACE` -- confirmed to already
    suppress every `ArmyType`'s recruit-compatibility check
    (`turn/recruit.py is_army_type_compatible_with_race`), so no
    separate army-type field is needed. A land province needs a
    caller-chosen `new_land_race` from `SCAR_TERRAIN_LAND_COLLAPSE_
    RACES` (Orcish/Dragons/Trollish) -- which of the three is left
    unresolved ("usually by immigration from an adjacent province"
    describes an external fact this function can't compute alone, not
    a formula to guess at); raises `ValueError` if omitted or invalid.
    For Dragons/Trolls, "the army type will change to something
    suitable" needs no new state either -- `models/army_type.py
    MONSTROUS_ARMY_RACE` already ties each to exactly one `ArmyType`
    via the same compatibility check, so changing `province.race`
    alone is sufficient; Orcish has no single such type (a genuine,
    documented gap, not guessed).
  - 8 new tests in `tests/test_cast_execution.py`. Full suite: 2442
    passed (2434 unchanged + 8 new).
- **Phase 202**: modeled Gate Demon [GD] (`Spell.GATE_
  DEMON`), tied to `Ability.NECROMANCY` -- the second secret Personal-
  Combat spell, similar in shape to Mirror Image. User-supplied: "Summon
  Demon... an extra-dimensional gate is opened to the nether worlds,
  from where a demon is summoned to fight in place of the spellcaster.
  The caster has no control over what type of demon will appear. If the
  Demon wins, it will return to the Abyss from whence it came. If it
  loses, the caster must continue the fight at the current combat range.
  If another Mirror Image or Gate Demon spell is cast against it, both
  spells will be nullified. A Demon may refuse to fight an opponent of
  Evil to Undead alignment (50% chance)." Both `Spell.GATE_DEMON`,
  `AdvancedAbility.GATE_DEMON_SPELL`, and a display-label-only
  `GATE_DEMON_TABLE` already existed in the codebase from an earlier
  phase (pre-transcribed rule text, per this project's usual practice)
  -- this phase adds the actual mechanic.
  - `models/monster.py GATE_DEMON_TYPE_PERCENT`/`roll_gate_demon_type
    (rng)` implements the rulebook's own d100 table (1-20 Imp, 21-40
    Succubus, 41-55 Bone Devil, 56-70 Ice Devil, 71-80 Marilith Demon,
    81-90 Rakshasha, 91-100 Balrog Demon) with the same cumulative-
    percentage-walk style as `roll_monster_alignment()`. Lives in
    `models/monster.py` rather than `models/advanced_ability.py`
    (which is 100% declarative and already imports from `monster.py`,
    so the reverse import would be circular). All seven demon species
    (`Monster.IMP/SUCCUBUS/BONE_DEVIL/ICE_DEVIL/MAR_DEMON/RAKSHASHA/
    BAL_DEMON`) already had `MONSTER_COMBAT_STATS` entries and are the
    exact same seven-species set as `HAND_OF_DEATH_ANTI_HOLY_MONSTERS`
    (Phase 190).
  - `turn/encounter.py resolve_gate_demon_refusal(rng)` implements the
    50% opponent-alignment-gated refusal roll (`GATE_DEMON_REFUSAL_
    CHANCE = 0.5`) as a pure roll -- the caller is responsible for first
    checking the opponent's alignment is Evil to Undead inclusive
    (`{Alignment.EVIL, Alignment.ANTI_HOLY, Alignment.UNDEAD}`, ordinals
    5-7 per the real Pascal `ALIGNMENT_ORDINAL` sequence, not `Alignment`'s
    own declaration order) before calling this function, mirroring the
    project's existing "pure roll, caller supplies the gating condition"
    convention.
  - Two real worked examples confirmed from this project's own sample
    turn-report files: a refusal case in `SE3__T10.K1` (the summoned
    demon declines to fight an Evil-aligned opponent) and a full-combat
    case in `SE3__T11.K1` (a Rakshasha fights with its own stat block
    "in place of" the caster, who still receives post-combat credit).
  - `GATE_DEMON_WINNER_RETURNS_TO_ABYSS`, `GATE_DEMON_LOSS_CASTER_
    RESUMES_FIGHT_AT_CURRENT_RANGE`, and `GATE_DEMON_NULLIFIED_BY_
    SIMULTANEOUS_MIRROR_IMAGE_OR_GATE_DEMON` are recorded as confirmed
    facts (`= True` sentinels with docstring citations), **not modeled
    as executable mechanics** -- same "clean, testable primitives only"
    boundary as every other Personal-Combat spell in this module: there
    is no real duel-orchestration engine yet to consume a "demon fights
    in place of the caster, then the caster resumes at the current
    range" state machine, a spell-nullification check against a
    simultaneously-cast opposing spell, or a "who gets credit" ledger.
  - No skill-level scaling (so `PERSONAL_COMBAT_SPELL_LEVEL_CAP`
    doesn't apply), matching Charm/Psychic Blast/Telekinetic Storm/
    Invisibility/Words of Healing's own uncapped, non-scaling effects.
  - The demon's own combat stat block is not synthesized by this
    module -- `turn/search_execution.py`'s existing inline
    Combatant-from-Monster construction pattern (`hit_points=rng.
    randint(*stats.hit_points_range)`, etc., reading from
    `MONSTER_COMBAT_STATS`) is cited in the docstring as the pattern a
    future orchestrator should reuse, not duplicated or extracted here
    since nothing yet consumes it.
  - 4 new tests in `tests/test_monster.py` (table sums to 100 +
    threshold walk + single-roll-consumption + anti-holy-membership),
    4 new tests in `tests/test_encounter.py` (constants + refusal
    threshold + single-roll-consumption). Full suite: 2450 passed
    (2442 unchanged + 8 new).
- **Phase 203**: modeled Lava Pool [LP] (`Spell.LAVA_POOL`),
  tied to `Ability.ELEMENTAL` -- the first Elemental secret spell,
  Personal-Combat, the thirteenth overall. User-supplied: "Instant
  Death if successful... The spell won't work against flying,
  underwater, ghostly or anti-holy monsters, and there is usually a
  chance to escape it (from 5% to 60%)," plus a 29-species immune list.
  The immune-species set (`models/advanced_ability.py LAVA_POOL_
  IMMUNE_MONSTERS`) already existed from an earlier pre-transcription
  phase and matches the user's own list name-for-name -- no changes
  needed there.
  - **Real source found for the escape-chance range, more precise than
    the user's own paraphrase**: this project's own sample turn report
    `SE3__T9.K6` (Desktop root) contains the actual level-6 Elemental
    Magic Advanced-Ability grant announcement, quoting "there is
    usually a chance to escape it (30% chance for medium-speed
    opponents, 60% for fast opponents)." `turn/encounter.py
    LAVA_POOL_ESCAPE_CHANCE: dict[MonsterSpeed, float]` transcribes
    that real source (`MonsterSpeed.MEDIUM: 0.30`, `MonsterSpeed.FAST:
    0.60`), not the user's rounder "from 5% to 60%" summary.
  - **`MonsterSpeed.SLOW: 0.0` is an inference, explicitly flagged, not
    a direct quote** -- neither the rulebook text nor `SE3__T9.K6`'s
    own real excerpt ever states a Slow percentage; only two tiers are
    named. Modeled as 0.0 because the source's own framing ("there is
    usually a chance to escape it") introduces an escape chance only
    for the two tiers it goes on to name, so the tier it's silent on is
    read as having none -- documented in the docstring as an inference
    so it doesn't read as a third sourced data point.
  - `lava_pool_escape_chance(speed)`/`resolve_lava_pool_escape(speed,
    rng)` -- the victim's own speed-keyed escape roll. No skill-level
    scaling on the caster's side (`PERSONAL_COMBAT_SPELL_LEVEL_CAP`
    doesn't apply): the rulebook ties this chance to the *victim's*
    speed, not the caster's own skill, unlike every scaled spell above.
  - `LAVA_POOL_KILLS_INSTANTLY = True` records the spell's own
    Advanced-Ability tagline ("Instant Death if successful",
    `models/advanced_ability.py ADVANCED_ABILITY_TAGLINE`) as a
    confirmed fact: a failed escape is a full, immediate kill, not a
    damage roll -- no `LAVA_POOL_DAMAGE_*` constant was invented.
  - Immunity itself (`target_is_immune`) and the base cast-success roll
    stay the caller's job, same "caller supplies the otherwise-
    unavailable precondition" pattern every Personal-Combat spell above
    uses (this module imports nothing from `advanced_ability.py`).
  - **Not wired into `turn/search_execution.py`'s combat resolution
    this phase either**, same reason as every other Personal-Combat
    spell above.
  - 6 new tests in `tests/test_encounter.py` (constants + lookup +
    Fast/Medium threshold walks + Slow-never-escapes + single-roll-
    consumption). Full suite: 2456 passed (2450 unchanged + 6 new).
- **Phase 204**: modeled Mystic Winds [MW] (`Spell.MYSTIC_
  WINDS`), tied to `Ability.ELEMENTAL` -- the second Elemental secret
  spell, but unlike Lava Pool (Personal-Combat) and every other secret
  spell so far, explicitly not a combat spell ("questo non è un
  incantesimo da combattimento," the user's own framing). User-
  supplied: "Wind-Walking Armies. By the mysterious power of the
  'Mystic Winds' spell, the great Wind Spirits of the heavens carry
  the mage or a co-located character into the sky... Each unit led by
  the affected leader has its movement set at 5 while the spell lasts
  and moves as an air unit. No fleet transport or air transport takes
  place: that is, each unit will use up movement points while under
  the effect of this spell. The spell ends just before the leader
  gets involved in any military battle between armies." Targets "the
  mage or a co-located character" -- a character-target spell, the
  same shape as Oratory/Illus_Armies, added to `turn/cast_decode.py
  CHARACTER_TARGET_SPELLS` rather than `NO_TARGET_SPELLS`/
  `PROVINCE_TARGET_SPELLS`.
  - `turn/cast_execution.py _execute_mystic_winds` mirrors Oratory's
    own "direct persistent state write" precedent rather than a
    strength-pipeline multiplier: on success it sets `LeaderState.
    mystic_winds_active = True` and, for every `ArmyState` the target
    currently commands (`state.armies_commanded_by`, a snapshot at
    cast time), hard-sets `ArmyState.movement_points =
    MYSTIC_WINDS_MOVEMENT_POINTS` (5) -- matching "has its movement
    set at 5" verbatim (a set, not an addition). No idempotency guard
    is needed, unlike Oratory's own `oratory_boosted_this_turn` flag:
    setting an absolute value twice already has the same effect as
    once, confirmed by a repeated-cast test.
  - **Three of the spell's own clauses are confirmed facts, not
    modeled, each for a different real reason**:
    `MYSTIC_WINDS_MOVES_AS_AIR_UNIT = True` -- this project's only
    "air unit" concept (`models/army_type.py OVERFLIGHT_AIR`) is a
    static per-`ArmyType` property with no per-leader override
    mechanism, and mutating `ArmyState.army_type` itself to fake it
    would corrupt every other lookup keyed by that field.
    `MYSTIC_WINDS_USES_MOVEMENT_POINTS_NORMALLY = True` -- this
    project has never built a fleet-transport or air-transport
    mechanic anywhere (the term appears only in a report-narration
    template, never as executable logic), so there is nothing to
    disable. `MYSTIC_WINDS_ENDS_BEFORE_ARMY_BATTLE = True` -- doing
    this correctly needs clearing the flag at every one of this
    project's several distinct battle-entry points (`fight_battle`,
    `fight_multi_attacker_battle`, forced-rebattle, army-vs-army
    Pursue), the same scale of cross-cutting change as Defend's own
    Phase 67/72 cancellation wiring, deliberately deferred rather than
    attempted as a same-phase add-on. Also cross-referenced by
    `models/advanced_ability.py`'s own still-unbuilt Illusory Fog spell
    ("air units... and those affected by 'Mystic Winds' Spell... have
    their strength halved").
  - 6 new tests in `tests/test_cast_execution.py` (constants + movement
    set on every commanded army + self-target + not-co-located failure
    + target-not-found failure + repeated-cast non-cumulative check).
    Full suite: 2462 passed (2456 unchanged + 6 new).
- **Phase 205**: modeled Augur Combat [AC] (`Spell.AUGUR_
  COMBAT`), tied to `Ability.PSYCHIC` -- the first Psychic secret
  spell, Personal-Combat, the fourteenth overall. User-supplied: "The
  Psychic Mage performs a powerful augury (forecast), whereby he
  divines the probable outcome of the combat. The computer will
  estimate the percentage chance of victory, if combat were to occur.
  If the plan following the spell is a combat-oriented plan, then if
  the chances are too low for the character's courage, he will shirk
  combat (Coward 80%, Cautious 60%, Brave 40%, Berserk 20%)... Usually
  this spell should be the first tactic ordered, when it won't cost
  you a combat round; if it comes later, then the result will be an
  attempt to flee." Plus the user's own follow-up clarification
  (Italian): the "estimate" is not a number shown to the player but a
  binary internal outcome from a silent simulation -- only a simulated
  *loss* ever triggers the courage-gated shirk roll.
  - `turn/encounter.py AUGUR_COMBAT_SHIRK_CHANCE: dict[Temper, float]`
    (Coward 80%, Cautious 60%, Brave 40%, Berserk 20%, `models/
    temper.py Temper`, Phase 82) and `augur_combat_shirk_chance(temper)`/
    `resolve_augur_combat_shirk(temper, rng)` -- the courage-gated roll
    itself, monotonic with `Temper`'s own ordinal. No skill-level
    scaling (the chance is keyed to Temper, not Psychic skill), so
    `PERSONAL_COMBAT_SPELL_LEVEL_CAP` doesn't apply.
  - `resolve_augur_combat(would_lose_simulated_combat, temper, rng)`
    composes the two together: returns `False` immediately (never
    consumes a roll) when the caller-supplied simulated outcome is a
    win, otherwise rolls the shirk chance. **The silent battle
    simulation itself is the caller's job, not this function's** --
    this project already has real combat resolvers (`resolve_melee_
    duel`, `turn/battle_orchestrator.py fight_battle`), but "simulate
    the probable outcome of the combat" names no specific one of them,
    and there is no Cast-tactic orchestration engine to make that
    choice from real plan/state data -- the same "caller supplies the
    otherwise-unavailable precondition" pattern every spell above uses,
    for a richer precondition than a single boolean fact this time.
  - **The "first tactic in the plan" position rule is a confirmed
    fact, not modeled**: `AUGUR_COMBAT_FREE_WHEN_CAST_FIRST = True`
    ("won't cost you a combat round") and `AUGUR_COMBAT_ACTS_AS_
    FLEE_WHEN_CAST_LATER = True` ("the result will be an attempt to
    flee"). Both need this cast's own position within a Special
    Encounter Plan's tactic list, the same already-confirmed gap
    `turn/search_execution.py`'s own docstring flags for every `CAST`
    entry in a guardian's plan.
  - 7 new tests in `tests/test_encounter.py` (constants + lookup +
    Cowardly/Berserk threshold walks + single-roll-consumption + the
    composed function's win-never-rolls and loss-rolls-through cases).
    Full suite: 2469 passed (2462 unchanged + 7 new).
- **Phase 206**: modeled Locate Object [LO] (`Spell.LOCATE_
  OBJECT`), tied to `Ability.PSYCHIC` -- the second Psychic secret
  spell, not a combat spell (confirmed by the user's own framing).
  User-supplied: "By the enchanting power of this spell, the
  provincial location of any magic item will be revealed to the
  spellcaster, as well as who is guarding the item, if anyone. If the
  magic item was lost to a wandering monster, it will be seen as
  guarded by a monster. The Psychic must specify the identifying
  number of the magic item, not the treasure name itself... this is
  because there is sometimes more than one of the same magic item in
  the game." Unlike every spell above, this one targets an
  item-instance id (`models/item.py ItemInstance.item_id`), not a
  character/province/nothing -- added to `turn/cast_decode.py`'s new
  `ITEM_TARGET_SPELLS`, a fourth target-shape category.
  - `turn/cast_execution.py _execute_locate_object` gates the usual
    cast-success roll but mutates nothing in `state` -- a pure
    information query, unlike every mutating spell above.
  - The real answer is a separate primitive, `locate_object(state,
    item_id) -> LocateObjectResult | None`, deliberately outside
    `CastExecutionResult`'s own shared applied/reason shape (that
    dataclass carries no per-spell payload by design). Looks up
    `GameState.items` (Phase 140's item-ownership registry) and, for a
    leader-held item, returns `LocateObjectResult(location, holder_
    leader_id)` -- the holder's own `LeaderState.location`.
  - **Only the leader-held half of "who is guarding the item, if
    anyone" is answerable at all -- confirmed absent, not guessed.**
    `models/item.py`'s own module docstring already scoped
    `ItemInstance` to leader-held items only when it was built: the
    real Pascal structure also tracks feature/monster-guarded treasure
    via a `feature_id + 256` owner-array convention, explicitly never
    modeled here ("this project has no monster/feature loot-generation
    pipeline at all"). `locate_object()` returns `None` for both an
    unknown `item_id` and a known item with `owner_leader_id is None`
    -- this project has no data to distinguish "lost to a wandering
    monster" from any other unowned case.
  - 4 new tests in `tests/test_cast_execution.py` (cast succeeds and
    mutates nothing + finds a leader-held item + unknown item id +
    feature/monster-guarded item returns `None`). Full suite: 2473
    passed (2469 unchanged + 4 new).
- **Phase 207**: modeled Illusory Fog [IF] (`Spell.ILLUS_
  FOG`), tied to `Ability.ILLUSION` -- the first Illusory secret
  spell, not a combat spell (confirmed by the user's own framing), a
  province target the same shape Scar Terrain already established.
  User-supplied: "Slow and Weaken Air Armies. By the murky power of
  the 'Illusory Fog' spell, the Illusionist summons a dense fog to
  blanket a province, reaching up to the very heavens. All air units
  (Dragon Wings, Eagle Wings and those affected by 'Mystic Winds'
  Spell) have their strength halved for any battle in the affected
  province, and must expend 1 additional movement point when entering
  or leaving it. The movement point is deducted after the unit(s) have
  already moved. The spell must be cast on an adjacent or co-located
  province, and it dissipates at the end of the gameturn." Added to
  `turn/cast_decode.py PROVINCE_TARGET_SPELLS`.
  - `turn/cast_execution.py _execute_illus_fog` mirrors `_execute_
    scar_terrain`'s own "co-located or adjacent province" pattern
    exactly: resolves the target, rolls cast success, and on success
    sets the new `ProvinceState.illusory_fog_active = True` -- a
    persistent flag, the same "spell writes real state, no consuming
    pipeline exists yet" shape `illusory_terrain`/`scar_terrain_gold_
    reduction` already use.
  - **The strength-halving effect has real, testable primitives, not
    yet wired into the battle-strength pipeline.**
    `ILLUSORY_FOG_STRENGTH_MULTIPLIER = 0.5`,
    `is_illusory_fog_affected_air_unit(army_type, mystic_winds_
    active)` (combines `models/army_type.py OVERFLIGHT_AIR` membership
    with a caller-supplied Mystic Winds flag, since this project has
    no per-army way to derive that flag itself -- the same gap Mystic
    Winds' own Phase 204 addendum already flagged), and
    `illusory_fog_strength(base_strength, affected=...)`. None of this
    is called from `turn/strength.py`/`turn/battle_orchestrator.py`
    yet, since neither consults `ProvinceState.illusory_fog_active` or
    a per-army Mystic-Winds flag anywhere today.
  - **The movement surcharge and end-of-turn dissipation are confirmed
    facts, not modeled.** `ILLUSORY_FOG_EXTRA_MOVEMENT_COST = 1`
    ("1 additional movement point when entering or leaving it...
    deducted after the unit(s) have already moved") has no movement
    pipeline to hook into (`turn/movement.py`/`turn/move_execution.py`
    consult no per-province spell effect at all).
    `ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN = True` records "it
    dissipates at the end of the gameturn" -- the same unresolved
    end-of-turn-cleanup gap `tax_modifier_percent`/`illusory_terrain`
    already carry.
  - 8 new tests in `tests/test_cast_execution.py` (constants + cast
    sets the province flag + out-of-range failure + air-unit
    classification for both Dragon/Eagle Wing and Mystic-Winds-active
    cases + ordinary-unit exclusion + strength halving both ways).
    Full suite: 2481 passed (2473 unchanged + 8 new).
- **Phase 208**: modeled Illusory Hero [IH] (`Spell.ILLUS_
  HERO`), tied to `Ability.ILLUSION` -- the second and last Illusion
  secret spell, Personal-Combat, and the last of all ten secret spells
  (25-34), explicitly "similar to Mirror-Image Phantasm." User-
  supplied: "By the wondrous magic power of this spell, the
  Illusionist creates an image of whatever Valhalla hero is currently
  in the world, to fight in his place. It is similar to 'Mirror-Image
  Phantasm', except that 15% is subtracted from the chance to
  disbelieve, and the illusory hero will usually not turn on its
  master if the illusion wins (unless the alignments of the illusion
  and the spellcaster are implacably hostile, for example Good versus
  Evil)."
  - `turn/encounter.py ILLUSORY_HERO_DISBELIEF_REDUCTION = 0.15` and
    `illusory_hero_disbelief_chance(base_chance, caster_skill_level)`/
    `resolve_illusory_hero_disbelief(...)` call through to Mirror-
    Image's own `mirror_image_disbelief_chance()` (same base-chance
    table, same per-level reduction) and then subtract one further
    flat 15 percentage points, clamped to [0%, 100%] -- reusing the
    existing formula rather than duplicating its table, since "except
    that 15% is subtracted" reads as a modifier on Mirror-Image's own
    already-computed chance. Confirmed: the two-stage clamp means this
    chance can never actually reach 100%, unlike Mirror-Image itself.
  - `ILLUSORY_HERO_TURNS_ON_MASTER_BY_DEFAULT = False` inverts Mirror-
    Image's own unconditional Stage-2 "the illusion then turns on the
    caster" rule. **The "unless... implacably hostile" exception is a
    confirmed exception, not a general alignment-hostility classifier**
    -- only one worked example is given ("Good versus Evil"), and
    `models/alignment.py` has no existing "implacably hostile pair"
    table to draw on; inventing a boundary from a single example would
    be guessing, not transcribing a sourced rule.
  - **"Whatever Valhalla hero is currently in the world" is a
    confirmed fact, not a lookup performed here.** This project's own
    VALHALLA subsystem (Phases 194-199) already establishes that the
    current visiting hero, when one exists, is always
    `state.leaders.get(models.valhalla.VALHALLA_VISITOR_LEADER_ID)`
    (199). Building the illusion's own `Combatant` from that hero's
    stats is left unbuilt, the same "clone a `Combatant` from a real
    stat source" pattern Gate Demon's own summoned monster (Phase 202)
    already leaves unbuilt -- no orchestration engine consumes either.
  - 6 new tests in `tests/test_encounter.py` (constants + the extra
    -15% reduction + clamps to 0% + never reaches 100% (a two-stage-
    clamp consequence, not a direct source figure) + single-roll-
    consumption at both bounds). Full suite: 2487 passed (2481
    unchanged + 6 new).

**All ten secret spells (25-34) are now modeled**: Gate Angel [GA]
(Phase 194-199), Words of Healing [WH] (200), Scar Terrain [ST] (201),
Gate Demon [GD] (202), Lava Pool [LP] (203), Mystic Winds [MW] (204),
Augur Combat [AC] (205), Locate Object [LO] (206), Illusory Fog [IF]
(207), and Illusory Hero [IH] (208).
- **Phase 209**: built the CAST-tactic orchestration engine for
  Search encounters -- `turn/search_execution.py`'s `execute_search()`
  previously skipped every `Maneuver.CAST` tactic silently (both the
  leader's own and the guardian's own, per `turn/cast_execution.py`'s
  own long-standing docstring: "casting them requires the general
  tactic-sequence combat engine... None of these ten can be attempted
  without building that engine first"). This phase wires 8 of the 10
  Personal-Combat-only spells -- Holy Symbol, Spiritwrack, Psychic
  Blast, Telekinetic Storm, Invisibility, Fireball, Ice Suspension,
  Control Undead -- plus Charm's own Personal-Combat form, into real
  Search combat. Hand of Death and Mirror-Image/Illusory Hero are
  deliberately deferred to a future Phase 210: both need a genuine
  round-based sub-loop (channeled attack, or a cloned-illusion duel
  with a per-round disbelief re-roll), unlike the eight spells here,
  which each resolve with a single roll.
  - `turn/encounter.py PERSONAL_COMBAT_SPELL_ABILITY: dict[Spell,
    Ability]` -- sourced directly from `cast_execution.py`'s own
    docstring citation grouping (`[4.21.4]-[4.21.5]` through
    `[4.25.4]-[4.25.5]`, five Ability blocks of two spells each),
    cross-referenced against `_SPELL_ABILITY`'s own confirmed entries
    for the other spells sharing each block number: WHITE (Holy
    Symbol, Spiritwrack), PSYCHIC (Psychic Blast, Telekinetic Storm),
    ILLUSION (Invisibility, Mirror-Image), ELEMENTAL (Fireball, Ice
    Suspension), NECROMANCY (Hand of Death, Control Undead).
  - `Combatant` gains four new fields, all no-op by default:
    `defensive_hit_multiplier` (Holy Symbol's self-buff, Invisibility's
    halving), `melee_damage_dealt_reduction` (Spiritwrack, applied to
    the *target*), `blocked_from_cast_and_archery` (Spiritwrack's own
    victim effect), `bonus_unanswered_attacks` (Psychic Blast, Ice
    Suspension's slowed/flying branches). `roll_melee_attack()`/
    `roll_fire_arrow_attack()` gain an optional `hit_chance_multiplier`
    parameter (default 1.0); `resolve_melee_duel()`/
    `resolve_fire_arrow_duel()` now pass the defender's own multiplier
    and subtract the attacker's own damage reduction automatically --
    every pre-Phase-209 caller (including `challenge_execution.py`)
    is unaffected by the new defaults.
  - `search_execution.py`'s new `_resolve_cast_tactic()` rolls
    `resolve_personal_combat_spell_cast()` (skill level from
    `LeaderState.skills.pair_for_ability()` for a leader caster,
    `models/monster.py MONSTER_MAGIC_ABILITIES` for a monster caster)
    and dispatches each spell's own effect on success, reusing
    `execute_search()`'s existing `_outcome_from()` for any
    instant-resolution outcome (a synthetic zero-round
    `EncounterCombatResult`). Three user-confirmed simplifications
    (via `AskUserQuestion`, no source gives a mechanic for these):
    Charm's own "equivalent to an FL that always succeeds" makes the
    *caster* flee (not the target); Control Undead's "neutralizes"
    success is treated as an outright win; Ice Suspension's own
    "frozen" branch (the caster's fuga-con-bottino/attesa choice, with
    no item-seizure system to hook into) is likewise simplified to an
    outright win, leaving the "rallentato"/flying branches fully
    modeled. "Bonus attack rounds" (Psychic Blast, Ice Suspension) are
    interpreted as free unanswered Melee swings, consumed immediately
    after the cast -- the source text names no specific tactic, and
    Melee is the natural fit since Fire Arrow already has its own
    separate free-shot cycle.
  - **Wiring**: the leader's own `Maneuver.CAST` tactics resolve in
    `request.tactics`'s own walk order (a new branch alongside
    `FLEE`/`SHOOT`/`MELEE`, gated on `blocked_from_cast_and_archery`).
    The guardian's own rolled-plan `CAST` tactics (`monster_plan`,
    Phase 178) are collected once and resolved right before the first
    real combat phase actually begins -- the same injection point
    already established for `monster_wants_shoot`'s own Fire Arrow
    check, so a leader's own earlier CAST always resolves before the
    guardian's.
  - **Known, documented limits, not addressed this phase**: the
    Dryad/Mermaid encounter plans' own repeated-Melee-then-later-Charm
    shape stays architecturally unreachable (`resolve_melee_duel()`
    still fights an entire duel to the death in one call); no real
    `CombatRange` transition state machine exists, so Telekinetic
    Storm's own caster self-damage assumes `CombatRange.SPELL_RANGE`
    fixed at cast time (every real CAST tactic precedes Arco/Mischia in
    a plan); Ice Suspension's item-seizure clause remains unconsumed
    (already true since Phase 189); Invisibility's Steal/Flee bonuses
    stay out of scope (no Steal resolver; Flee-bonus stacking deferred).
  - Two pre-existing tests (`test_search_execution.py`'s own
    `test_execute_search_monster_wanting_shoot_fires_even_when_the_
    leaders_plan_never_does`/`..._does_not_double_resolve_when_leader_
    plan_also_shoots`) needed updating: Titan's own rolled plan opens
    with real CAST tactics now, so the generic cast-success roll is
    forced to fail in both to isolate their own Fire-Arrow-ordering
    concern from CAST's newly-live behavior.
  - 9 new tests in `tests/test_encounter.py` (the four new `Combatant`
    field defaults, `PERSONAL_COMBAT_SPELL_ABILITY`'s full contents,
    `hit_chance_multiplier` on both attack rollers at 0.0/very-high,
    `resolve_melee_duel`/`resolve_fire_arrow_duel` respecting
    `defensive_hit_multiplier`/`melee_damage_dealt_reduction`) plus 21
    new tests in `tests/test_search_execution.py` (one per spell +
    Charm across their own success/failure/eligibility branches, the
    leader-CAST-before-guardian-CAST ordering, and
    `blocked_from_cast_and_archery` skipping the guardian's own later
    CAST tactic). Full suite: 2517 passed (2487 unchanged + 30 new).
- **Phase 210**: wired the last two Personal-Combat spells --
  Hand of Death [HA] and Mirror-Image Phantasm [MI] -- completing all ten
  of `turn/cast_execution.py`'s own "Personal-Combat-only" spells. Both
  needed a genuine round-based sub-loop (Phase 209 deliberately deferred
  them for exactly this reason): Hand of Death channels a repeated attack
  exchange that ends the instant the caster is hit; Mirror-Image runs a
  two-stage duel (a cloned illusion fights the real opponent, then, if it
  wins, turns on its own caster) with a per-round disbelief re-roll
  before each exchange.
  - `turn/encounter.py resolve_hand_of_death_channel(caster, victim,
    skill_level, rng, *, target_is_immune=False, max_rounds=1000)`: the
    caster's own attack always lands (no hit-chance roll -- a psychic,
    not physical, blow) for `roll_hand_of_death_damage()`'s own uncapped
    `1 + 0.5*level`; the victim's own halved-chance Melee counter-attack
    (`HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER`) ends the channel the
    instant it lands, real damage and all -- "perde la concentrazione e
    l'incantesimo svanisce." Initiative substitutes the caster's own
    Necromancy skill level for Melee (`hand_of_death_caster_melee_
    defense_skill()`, already built in Phase 190). Returns
    `winner="a"` (caster) only if the victim dies outright; `winner=None`
    the instant the channel breaks or `max_rounds` is exhausted --
    either way the caller falls through to a normal tactic (typically
    Melee), with both sides' hit points carrying over unchanged.
  - `turn/encounter.py resolve_mirror_image_duel(caster, opponent,
    opponent_tier, skill_level, rng, *, max_rounds=1000)`: Stage 1 clones
    `opponent` into a throwaway `illusion` and duels it against the real
    `opponent` (only their hit points change -- the caster "performs no
    other actions"); a per-round disbelief roll (`resolve_mirror_image_
    disbelief()`, already built Phase 187) can end this stage early.
    If the illusion loses or is disbelieved, `winner=None` (3a: "the
    caster must continue the fight at the current combat range") --
    whatever damage the opponent already took carries into the next real
    fight. If the illusion wins (opponent's hit points reach 0), Stage 2
    has it turn on the real caster, using the same disbelief roll at
    `MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE` (Medium Human's 80% + a
    flat 25-point bonus) interleaved with a real caster-vs-illusion Melee
    duel. `winner="a"` if the caster disbelieves or slays the illusion
    (auto-claims the treasure); `winner="b"` if the illusion instead
    kills the caster (the opponent's own "revival" has no stated
    magnitude, so isn't modeled as a hit-points change -- it doesn't
    change this function's reported winner either way).
  - `turn/encounter.py MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER: dict[
    Monster, MirrorImageIntelligenceTier]` -- all 60 real species,
    project-original (user-supplied, a Desktop "Intelligenza mostri.txt"
    file), since this project had no source at all for four of the six
    tiers (only Animal/Mechanical existed via Spiritwrack's own Phase 182
    sets). **Confirmed to diverge from Spiritwrack's own Animal-
    Intelligence set for three species**: Giant Worm, Giant Amoeba, and
    Giant Clam are Spiritwrack-Animal but Mirror-Image-Mechanical -- a
    real, sourced difference between the two classifications, not a
    reuse (the module docstring's own Phase 187 addendum had already
    flagged this exact risk: "Cross-reference, not reuse"). **A King or
    Hero opponent's own tier is confirmed by the user, corrected same-day
    from this phase's own first pass**: always `MirrorImageIntelligenceTier
    .HIGH_HUMAN` (not the inferred Medium Human default first shipped
    here), plus a further flat bonus on top of that table value from the
    leader's own real Sage/Illusion skill levels -- "C'e' un bonus di +2%
    sulla tabella per ogni livello in SA e +1% per ogni livello in IL."
    `mirror_image_leader_disbelief_bonus(sage_level, illusion_level)`
    computes it; `resolve_mirror_image_duel()` gained an `opponent_
    disbelief_bonus` keyword (default `0.0`, every other caller
    unaffected) added directly to the table value before the caster's own
    per-level reduction. Monster opponents don't get this bonus -- it's
    specific to Kings/Heroes.
  - `turn/search_execution.py`'s own `_resolve_cast_tactic()` gained two
    more branches, same `PERSONAL_COMBAT_SPELL_ABILITY`-driven dispatch
    as every Phase 209 spell: Hand of Death computes `target_is_immune`
    from `models/monster.py HAND_OF_DEATH_IMMUNE_MONSTERS` (a monster
    target) or `leader.alignment in {UNDEAD, ANTI_HOLY}` (a leader
    target), then calls the new channel resolver; Mirror-Image looks up
    `opponent_tier` from the new monster table (or the leader default)
    and calls the new duel resolver, translating its own `"a"/"b"`
    convention to the dispatcher's own `leader`/`monster` `"a"/"b"`
    convention exactly like Telekinetic Storm's own dual-outcome handling
    already does.
  - Illusory Hero [IH] (Phase 208) stays unwired -- it needs the same
    illusion-duel engine as Mirror-Image, plus its own "whichever hero is
    currently visiting Valhalla" combatant source, which nothing in this
    project builds yet.
  - One pre-existing test needed updating
    (`test_execute_search_cast_ice_suspend_immune_species_has_no_effect`):
    Spectre's own real rolled plan can now include real CAST tactics of
    its own, so `roll_monster_encounter_plan` is mocked empty to isolate
    that test's own "Ice Suspend has no effect" concern from the
    guardian's own newly-live CAST dispatch.
  - 13 new tests in `tests/test_encounter.py` (the channel resolver's
    immunity/kill/break/max-rounds branches, the intelligence-tier
    table's full coverage and its confirmed Spiritwrack divergence, the
    leader default, the duel resolver's disbelief/stage-1-loss/
    stage-2-win/stage-2-loss branches, plus the leader Sage/Illusion
    bonus formula and its own effect on the duel) plus 8 new tests in
    `tests/test_search_execution.py` (immune-flag threading, instant win,
    broken-channel fallthrough, and the Necromancy skill-level lookup for
    Hand of Death; sourced-tier/leader-default-plus-bonus lookup, instant
    win, and instant loss for Mirror-Image). Full suite: 2538 passed
    (2517 unchanged + 21 new).
- **Phase 211**: wired Illusory Hero [IH] -- the last of the ten
  secret spells (`AdvancedAbility.ILLUSORY_HERO_SPELL`, `Ability.ILLUSION`
  level 5+) and the last spell in this project with zero prior real
  execution. Module docstring's own Phase 208 addendum quotes the rule in
  full: "the Illusionist creates an image of whatever Valhalla hero is
  currently in the world, to fight in his place. It is similar to
  'Mirror-Image Phantasm', except that 15% is subtracted from the chance
  to disbelieve, and the illusory hero will usually not turn on its
  master if the illusion wins (unless the alignments of the illusion and
  the spellcaster are implacably hostile, for example Good versus Evil)."
  Two structural differences from Mirror-Image drove the design: the
  illusion is a fresh image of a *third party* (the current Valhalla
  visitor) rather than a clone of the opponent, and Stage 2 (the illusion
  turning on its own caster) is *conditional* on an alignment-hostility
  check rather than unconditional.
  - `turn/encounter.py resolve_illusory_hero_duel(caster, opponent, hero,
    opponent_tier, skill_level, rng, *, opponent_disbelief_bonus=0.0,
    turns_on_master=False, max_rounds=1000)`: reuses `resolve_mirror_
    image_duel()`'s own two-stage shape, but the Stage 1 illusion is built
    from `hero` at full `CHARACTER_HIT_POINTS` (an image, not a snapshot
    of the real visitor's own current wounds) instead of cloning
    `opponent`, and every disbelief roll uses `resolve_illusory_hero_
    disbelief()` (already built Phase 208 -- the same table plus a
    further flat 15% reduction) instead of the base Mirror-Image formula.
    If Stage 1's illusion wins **and** `turns_on_master` is False, that's
    an outright `winner="a"` with no Stage 2 duel at all -- the key
    structural difference from Mirror-Image, whose Stage 2 always fires.
    If `turns_on_master` is True, Stage 2 proceeds exactly like Mirror-
    Image's own (same `MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE`, since
    no separate number is given for Illusory Hero's own version of that
    branch).
  - `ILLUSORY_HERO_HOSTILE_ALIGNMENT_PAIRS: frozenset[frozenset[
    Alignment]]` and `illusory_hero_alignments_are_implacably_hostile(a,
    b)` -- project-original, user-supplied (the rulebook itself only
    confirms one worked example, "Good versus Evil"; this module's own
    Phase 187 addendum had already declined to invent a general hostility
    classifier from a single example). The confirmed table, six symmetric
    pairs: Divine vs Pagan/Evil/Undead, Good vs Evil/Undead, Undead vs
    Druid.
  - `turn/search_execution.py`'s own `_resolve_cast_tactic()` gained the
    `Spell.ILLUS_HERO` branch: looks up the current Valhalla visitor via
    `state.leaders.get(VALHALLA_VISITOR_LEADER_ID)` -- no visitor means no
    effect, the same "precondition can't be met" convention as every
    other spell above; a new `ILLUS_HERO_KNOWN_ABILITY_LEVEL = 5` gate
    (checked before the generic cast-success roll, same "ineligible means
    no roll at all" pattern as Control Undead) enforces the AdvancedAbility
    skill threshold this project had never wired for any spell before.
    `opponent_tier`/`opponent_disbelief_bonus` reuse Mirror-Image's own
    monster-table/leader-default-plus-Sage/Illusion-bonus lookup exactly;
    `turns_on_master` is computed from the hero's and caster's own
    recorded `Alignment` (unrecorded on either side defaults to not-
    hostile, same convention as every other alignment gate above).
  - 14 new tests in `tests/test_encounter.py` (the hostile-alignment-pair
    table and its symmetry, the duel resolver's disbelief/leader-bonus/
    stage-1-instant-win/stage-2-win/stage-2-loss branches) plus 8 new
    tests in `tests/test_search_execution.py` (no-visitor no-effect,
    level-gate blocks no roll, sourced monster tier, leader-target tier
    plus bonus, instant win/loss, and `turns_on_master` computed True/
    False from alignment). Full suite: 2554 passed (2538 unchanged + 16
    new).

**All ten Personal-Combat-only spells (Holy Symbol, Spiritwrack, Psychic
Blast, Telekinetic Storm, Invisibility, Fireball, Ice Suspension, Control
Undead, Hand of Death, Mirror-Image) plus Charm's own combat form and
Illusory Hero (the last of the ten secret spells) are now wired into real
Search combat** -- the CAST-tactic orchestration engine `turn/cast_
execution.py`'s own docstring named as the blocking gap since Phase 60 is
complete (Phases 209-211).
- **Phase 212**: closes the "render already-computed
  intelligence data into report prose" half of Trail's/ASpy's own
  long-flagged gap -- researched first and found the *data* layer for
  both was already fully complete (Trail's own five sourceable [3.17]
  fields since Phases 159/164/165/166; ASpy's own province facts and
  `SAY.PAS` line items since Phases 62/115/118), just never assembled or
  rendered.
  - **`describe_aspy(report, *, spy_name, province_name, rng) ->
    list[str]`** (`report/turn_report.py`, new): the first real assembly
    of Phase 115/118's own `SAY.PAS`-sourced ASpy templates
    (`render_spy_report_opening`/`_capital_province`/`_army_type`/
    `_elements_intro`/`_character_here`/`_no_characters(_or_forces)`/
    `_leads`/`_garrison`/`_report_closing`) -- every one of them already
    real and sourced, simply never called from anywhere before this
    phase. The assembly *order* itself is this project's own reasoned
    choice, not a directly-quoted `REPORTS.PAS` call sequence (no
    surrounding `Imp_Code` control-flow source survives, only the raw
    `Say(...)` constants) -- documented as such in the function's own
    docstring. Taxation (`_LSTax`) still never renders: `SpyReport`
    still carries no tax estimate (no per-province tax-base model
    exists anywhere in this project).
  - **`turn/aspy_execution.py`** gains the army-name data
    `describe_aspy()` needed but `SpyReport` never carried:
    `SpottedCharacter.army_names` (every army a spotted character
    leads) and `SpyReport.garrison_army_names` (every *unled* army at
    the spy's own province), both named via `models/army_naming.py
    make_army_name()` -- built Phase 149, never given a real caller
    until now. Race (needed only to decide whether a short non-Human
    tag is appended) resolves the same way `describe_armies_report()`'s
    own Phase 158 precedent already established (`MONSTROUS_ARMY_RACE`
    else the owning Kingdom's race), with an explicit `Race.HUMAN`
    fallback, flagged in `_army_display_name()`'s own docstring, for a
    mercenary army with no owning Kingdom to source a race from at all.
  - **Trail's own [3.17] intelligence payload gets project-original
    prose**, confirmed by direct user instruction ("Prosa originale del
    progetto") after confirming no `PROSE`/`SAY.PAS` source exists for
    these specific sentences anywhere in the available archive (unlike
    ASpy's own templates above). Eleven new hardcoded templates
    (`TRAIL_TEMPER_TEMPLATE` through `TRAIL_KING_NO_PROVINCES_TEMPLATE`)
    plus their `render_trail_*()` wrappers, assembled by the new
    **`describe_trail_intelligence(result, *, state, trailer_name,
    target_name, rng) -> list[str]`** -- a separate function from the
    pre-existing `describe_trail()` (which only narrates the catch-up
    moment itself, `_LCatch`), so that function's own signature/callers
    stay untouched. Narrates temper/alignment/race (skipped when `None`,
    the data layer's own "not recorded" convention) and treasures
    owned/armies led (always one line each, choosing a populated-list
    template or a dedicated "owns/leads none" template rather than
    skipping silently -- an empty list is itself a learned fact, not
    missing data). `result.king_intelligence` (only set for a King
    target) adds finances/allies/controlled-provinces the same way.
    [3.17]'s remaining named field, Actions, still isn't rendered --
    still structurally unbuildable, per `turn/trail_execution.py`'s own
    already-standing note (no per-phase action log exists anywhere in
    this project).
  - **Two stale docstring claims corrected** (this project's own
    "don't let a doc comment outlive the code" policy, Phase 55/153/159/
    160's own precedent): `turn/intelligence_estimate.py`'s docstring
    still said `LeaderState.alignment` didn't exist as of Phase 211,
    two phases after Phase 162 actually added it; `turn/
    search_execution.py _resolve_cast_tactic()`'s own docstring still
    said Illusory Hero "stays unwired here," a full phase after Phase
    211 wired it.
  - Non-breaking: full suite passed unchanged (2554 passed) before any
    new tests were written -- new fields/functions only, no existing
    caller touched. 30 new tests added (2584 passed total) across
    `tests/test_aspy_execution.py` (army-name data: leads, garrison,
    the mercenary Human-race fallback), `tests/test_turn_report.py`
    (every new `render_trail_*` function, `describe_trail_intelligence`
    across its None-field/empty-list/populated-list/King branches, and
    `describe_aspy` across its no-characters-or-forces/forces-without-
    characters/characters-with-and-without-armies/capital/recruitable-
    types branches).
- **Phase 213**: wires `PURSUE`/`TRAIL`/`SEARCH`/`ASPY` into
  `describe_turn_results()` -- the "built but never invoked from a real
  turn" gap that function's own docstring had named for those four
  actions (plus `TRADE`, still open) since Phase 143/147/156.
  - **`PursueExecutionResult`/`TrailExecutionResult`/
    `SearchExecutionResult` each gain a `request: XRequest | None =
    None` field**, populated by `plan_dispatch.py`'s own
    `_dispatch_pursue()`/`_dispatch_trail()`/`_dispatch_search()` --
    the one real call site every actual turn passes through -- rather
    than by `execute_pursue()`/`execute_trail()`/`execute_search()`
    themselves. **A deliberate, documented scope choice**: those three
    functions have a combined ~30 early-return sites across three
    modules; stamping the field at the dispatcher instead of at every
    one of those sites keeps this phase's diff to 3 small dispatcher
    edits, at the cost of `request` staying `None` for any direct
    `execute_*()` caller (every existing unit test included) -- those
    callers already had no way to get this data before this phase
    either, so nothing regresses.
  - **`describe_turn_results()`** gained four new branches:
    `PURSUE` resolves `target_name` via `request.target_character_id`
    and `province_name` via the caster's own current location (reusing
    `_province_label()`); `TRAIL` does the same, then also appends
    Phase 212's own `describe_trail_intelligence()` lines right after
    the catch-up sentence; `SEARCH` resolves `feature_id` ->
    `GameState.features` -> a `feature_name` via the exact same
    `_province_label()` coordinate/name fallback (a `Feature`'s own
    coordinate IS its containing province's coordinate, so this
    doubles as "use the province name if one is recorded" rather than
    inventing a separate feature-naming system this project has never
    had); `ASPY` needed no new field at all -- `SpyReport.province`
    (already a real `HexCoord`) was enough, resolved through
    `describe_aspy()` (Phase 212).
  - **`TRADE` stays unwired, a narrower gap than before**:
    `TradeExecutionResult` could get the same `request` treatment, but
    `describe_give()`'s own successful-item-transfer branch still needs
    a caller-supplied `item_name` this project has no synthesis for
    (`TradeExecutionResult` doesn't even record *which* `ItemInstance`
    moved) -- a distinct, still-open gap, documented in both functions'
    own docstrings, not attempted here.
  - Two further stale docstring claims corrected in passing (this
    project's own "don't let a doc comment outlive the code" policy):
    `describe_search()`'s own docstring and this module's own top-level
    docstring both still said SEARCH was structurally unwireable, for
    the same reason PURSUE/TRAIL/TRADE were -- no longer true as of
    this phase.
  - Non-breaking: full suite passed unchanged (2584 passed) before any
    new tests were written -- the new `request` fields default to
    `None`, and the new `describe_turn_results()` branches are pure
    additions no existing entry can reach. 11 new tests added (2595
    passed total): 3 in `tests/test_plan_dispatch.py` (confirming each
    dispatcher stamps `request`), 8 net-new in
    `tests/test_describe_turn_results.py` (the old
    `..._skips_pursue_trail_trade_entirely` test split into a
    TRADE-only version plus dedicated PURSUE/TRAIL/SEARCH/ASPY
    render/skip-without-a-request/skip-when-target-unknown cases).
- **Phase 214**: closes the last of the five gaps
  `describe_turn_results()`'s own docstring named since Phase 143 --
  `TRADE` is now wired in, using the exact same `request`-stamping
  pattern Phase 213 established for `PURSUE`/`TRAIL`/`SEARCH`.
  - **The "no item-instance display-name synthesis" gap Phase 213's
    own note claimed turns out to already be half-closed**:
    `models/treasure.py TREASURE_NAME` has mapped every `Treasure`
    type to a real display name since Phase 77 -- the only thing truly
    missing was *which* `ItemInstance` moved, not how to name it once
    known. `turn/trade_execution.py execute_give()` already resolves
    the real transferred `ItemInstance` as a local variable at its
    successful-item-transfer return site; it just never kept it.
  - **`TradeExecutionResult` gains two fields**: `item:
    ItemInstance | None = None` (the real transferred instance, `None`
    unless `item_transferred` is `True`) and `request: TradeRequest |
    None = None` (same dispatcher-stamped convention as
    `PursueExecutionResult.request`'s Phase 213 note) -- populated by
    `plan_dispatch.py`'s own `_dispatch_trade()`, not by
    `execute_give()` itself, for the same reasoning.
  - **`describe_turn_results()`** gained a `TRADE` branch: resolves
    `recipient_name` via `request.target_leader_id`, resolves
    `item_name` via `TREASURE_NAME[entry.result.item.treasure]` when
    `entry.result.item is not None`, then calls the pre-existing
    (Phase 142) `describe_give()` composer -- unlike the Phase 213
    branches, this one returns `str | None` and falls through to the
    loop's existing single-line `if line is not None: lines.append(line)`
    logic rather than `lines.extend(...); continue`.
  - `describe_give()`'s own docstring corrected in passing (stale
    "this project has no item-instance display-name synthesis" claim,
    same self-correction policy as Phase 213's two docstring fixes) --
    now documents that `describe_turn_results()` resolves `item_name`
    itself via `TREASURE_NAME`, and a direct caller only needs to
    supply it manually if it has no `TradeExecutionResult.item`.
  - Non-breaking: full suite passed unchanged (2595 passed) before any
    new tests were written, after fixing two pre-existing
    `test_trade_execution.py` equality assertions that predated the
    new `item` field (dataclass `==` now includes it, so the two
    successful-item-transfer tests needed `item=item` added to their
    expected `TradeExecutionResult`s -- a mechanical update, not a
    behavior change). 8 new tests added (2599 passed total): 1 in
    `tests/test_plan_dispatch.py` (`_dispatch_trade()` stamps
    `request`), 4 in `tests/test_describe_turn_results.py` (skip
    without a request, render a gold Give, render an item Give, skip
    when the recipient is unknown), plus the 2 corrected
    `test_trade_execution.py` assertions and 1 renamed test
    (`test_describe_turn_results_skips_trade_entirely` ->
    `..._skips_trade_without_a_request`, since the skip reason is now
    "no request stamped," not "no item-name synthesis").
- **Phase 215**: `report/turn_report.py compose_letter_report()`
  (new) -- the first top-level, per-kingdom letter-report assembler,
  stitching together this project's own already-built section
  composers.
  - **Sourced section order, not guessed**: `REPORTS.PAS`'s own driver
    that calls the ten real letter sections in sequence lived in the
    missing main program (same "the caller is lost, not the callees"
    situation as `turn/movement.py`'s hex adjacency scheme), so this
    phase cross-references the Desktop's real, actually-generated
    `SE3__T*.K*` turn-report output files instead (e.g. `SE3__T2.K2`,
    section headers found at lines 31/174/319/352/367/416/450/471/
    491/506): ACTION REPORT, LETTER REPORTS, DIPLOMACY, FINANCES,
    PROVINCES, CHARACTERS, ARMIES, IMPERIAL OFFICE REPORT, ADVENTURE,
    GENERAL INTELLIGENCE REPORT, in that order.
  - **Only 2 of the 10 real sections are wired**: ACTION REPORT (wraps
    `describe_turn_results()`, Phase 61/213/214, filtered here to only
    the given kingdom's own leaders since that function has no
    kingdom concept of its own) and ARMIES (wraps
    `describe_armies_report()`, Phase 158, unchanged). Every other
    section needs `GameState` data confirmed absent, not merely
    unwired -- documented explicitly in the new function's own
    docstring, section by section: LETTER REPORTS needs an
    inter-leader message queue; DIPLOMACY needs an Ally/War/Neutral
    relation table `KingdomState` doesn't have; FINANCES' real
    "Expected Revenues/Expenses" figures need `ACost`/`LCost`/
    `Tax_Base`, confirmed absent since Phase 158; PROVINCES and
    CHARACTERS each need a full per-province/per-leader stat table no
    composer builds yet; IMPERIAL OFFICE REPORT needs office-holder
    data no field tracks; ADVENTURE needs a per-province monster/
    feature listing (only the single-encounter `describe_search()`
    exists); GENERAL INTELLIGENCE REPORT needs a whole-turn
    aggregation of every `SpyReport`, and `describe_aspy()` only
    renders one at a time.
  - A section is omitted entirely (no header, no body) when its own
    composer has nothing to say, rather than emitting an empty
    section -- `describe_turn_results()`'s own existing per-phase
    convention, reused here at the section level.
  - Non-breaking: full suite passed unchanged (2599 passed) before any
    new tests were written -- a pure new-function addition, no
    existing caller touched. 4 new tests added (2603 passed total) in
    `tests/test_turn_report.py`: section order/stitching, ACTION
    REPORT omitted when this kingdom has no results, `results`
    filtered to only this kingdom's own leaders (a `PhaseDispatchResult`
    belonging to another kingdom's leader must not leak into this
    kingdom's letter), and ARMIES always present (even with zero
    armies, matching `describe_armies_report()`'s own "None at
    present" behavior).
- **Phase 216**: `report/turn_report.py
  describe_adventure_report()` (new) -- the "ADVENTURE" section,
  wired into `compose_letter_report()` right after ARMIES (matching
  the real letter's own relative order, skipping the still-unwired
  IMPERIAL OFFICE REPORT that sits between them in a real letter).
  - **Real double-gate this project doesn't model, and its own
    substitute**: the real `Desc_Adventure`'s own province gate
    (`provpres[px,py] and 16`, an undefined presence bitflag) and
    per-feature gate (`fdis[fn] > 0`, confirmed by `models/feature.py`'s
    own docstring to have an unresolved relationship to the per-kingdom
    `fdisc`/`discovered_by_kingdom` array this project already models)
    are both replaced by a single, documented interpretation:
    `Feature.discovery_level(kingdom_id) > 0`. Every province on the
    map is scanned, not just this kingdom's own -- feature discovery is
    independent of province ownership, matching the real procedure's
    own whole-board loop.
  - Sourced verbatim: the section header, its 3-line opening flavor
    text (rejoined, same convention as `_ARMIES_REPORT_OPENING`), the
    column-header line, and the "Renegade "/"Giant "/"Great "
    monster-name-prefix-stripping rule (`Desc_Adventure`'s own 4th
    truncation case, tied to fixed-width columns this composer doesn't
    reproduce, is dropped).
  - **Deliberately not reproduced**: the real "Special" column's
    richer cases (a magic-power hint at discovery level 2, a full
    treasure listing at level 3) and the "Guarding unknown riches"
    line -- both need a per-feature `MagicFeature` link and a
    feature's own treasure *instance*, both confirmed still unmodeled
    (`models/feature.py`'s own Phase 75/77 notes: world generation is
    the blocking gap). Only level 1's real, single-character `"?"` is
    rendered.
  - Non-breaking: full suite passed unchanged (2603 passed) before any
    new tests were written, after updating 2 pre-existing
    `compose_letter_report()` tests (Phase 215) whose expected output
    now needs the always-present ADVENTURE section appended -- a
    mechanical update, not a behavior change, same situation as Phase
    214's own two `test_trade_execution.py` fixes. 12 new tests added
    (2613 passed total) in `tests/test_turn_report.py`, covering:
    opening/header lines, empty-state "None at present", a discovered
    feature rendering, a looted feature, discovery-level-1's `"?"`,
    an undiscovered feature's exclusion, this-kingdom-only filtering,
    the monster-name-prefix strip, a feature with no guardian recorded,
    and province/feature sort order.
- **Phase 217**: `report/turn_report.py
  describe_letter_reports()` (new) -- the "LETTER REPORTS" section.
  - **A real, sourced structural discovery, not a guess**: reading
    `Write_Letter(ldr,kng,non)` in full revealed it doesn't read from
    any separate stored-message system at all -- it calls
    `Tell_Story(ldr,kng)`, the *exact same* story-buffer mechanism
    `Basic_Report()` already uses for the King's own "ACTION REPORT".
    A "letter" is simply another leader's own turn narrative, wrapped
    in a From/To/salutation/signature envelope. This project already
    had that narrative available via `describe_turn_results()`, so
    this composer reuses it directly rather than needing new state --
    this closes a gap that was originally (Phase 215's own note)
    thought to need a whole new inter-leader message queue.
  - **Correctness fix to `compose_letter_report()`'s own ACTION
    REPORT scope**: this research also surfaced that ACTION REPORT had
    been wrongly scoped kingdom-wide since Phase 215 (every leader's
    own results, not just the King's) -- which would have duplicated
    a Hero's own turn narrative in both ACTION REPORT and their own
    new LETTER REPORTS entry. Narrowed to just the `is_king`-flagged
    leader's own results; a kingdom with no King recorded now gets no
    ACTION REPORT at all (the real section is always about one
    specific King), rather than the old fallback of using every leader.
  - **Which leaders write a letter is an interpretation, not a
    citation**: the real gate (`Either_King(ldr,kng,false)`) has no
    surviving definition in any of the 13 available `.PAS` files.
    Modeled as "every other leader recorded in this kingdom, excluding
    the King himself" -- the natural reading given `Letter_Reports(kng)`
    is called once per King.
  - **Deliberately not reproduced**: `Check_Pigeons`'s own separate
    inter-player pigeon-message system (confirmed absent, no
    message-store concept exists anywhere in this project); the
    multi-turn backlog loop (only this turn's own results render, the
    same single-turn scope `describe_turn_results()` already has); the
    random "Squire to `<leader>`" alternate-authorship gimmick (needs
    fields this project doesn't track for this purpose -- every letter
    is signed with the leader's own real name).
  - A new shared `_king_leader_id(state, kingdom_id)` helper resolves
    the `is_king`-flagged leader for a kingdom, used by both
    `describe_letter_reports()` and `compose_letter_report()`'s own
    narrowed ACTION REPORT scope.
  - Non-breaking: full suite passed unchanged (2613 passed) before any
    new tests were written, after updating 4 pre-existing
    `compose_letter_report()` tests (Phase 215/216) whose expected
    output now needs the always-present LETTER REPORTS section (and,
    for the "real order" test, an explicit King leader plus a real
    Hero-to-King letter) -- a mechanical update reflecting the new
    section and the ACTION REPORT scope fix, not an unrelated behavior
    change. 7 new tests added (2620 passed total) in
    `tests/test_turn_report.py`, covering: no-other-leaders and
    other-leader-with-no-results empty states, a real rendered letter,
    the King's own results being excluded from his own letters,
    multiple Heroes each getting their own separate letter, other
    kingdoms' leaders being excluded, and the no-King-recorded
    fallback (letters still render, addressed to a blank "To:").
- **Phase 218**: `report/turn_report.py
  describe_diplomacy_report()` (new) -- the "DIPLOMACY" section,
  wired into `compose_letter_report()` between LETTER REPORTS and
  ARMIES (matching the real letter's own relative order, skipping the
  still-unwired FINANCES/PROVINCES/CHARACTERS that sit between
  DIPLOMACY and ARMIES in a real letter).
  - **A real 3-state relation this project only half-models**:
    `REPORTS.PAS`'s own `kallst[kng,k2]` tracks Allied/At War/Neutral
    per kingdom pair, but `GameState.allied_kingdoms` (a flat
    `set[frozenset[int]]`, Phase ~9's own `is_allied()`) only ever
    modeled a 2-state relation -- confirmed absent, no war-declaration
    mechanism exists anywhere in this project. AT WAR therefore always
    renders the real, sourced `"None at present"` string rather than a
    guess at zero wars; every other kingdom not in `allied_kingdoms`
    is listed as NEUTRAL instead, since there's no way to distinguish
    a genuine war from ordinary neutrality with the data available.
  - Sourced verbatim (`Rep_Allies`/`Begin_List`, `~REPORTS.PAS`
    line 104-119): the section header, all three intro sentences
    (each rejoined across its own 2 raw `WRITELN` lines, same
    convention as `_ARMIES_REPORT_OPENING`), and the empty-list
    fallback -- reused directly since it's the same real string
    `_ARMIES_REPORT_NONE_AT_PRESENT` already established.
  - **Deliberately not reproduced**: `Write_List`'s own optional
    per-entry enrichment (a known King's tax-base/treasury figure,
    gated on the *reader* holding the Emperor/Treasurer office and
    having met that King; an alignment note for Heavenly/Undead or
    same-alignment Kings) -- needs office-holder tracking (IMPERIAL
    OFFICE REPORT's own still-open gap) and per-King
    alignment-visibility state this project doesn't model. Only the
    bare `<name> (#<kingdom_id>)` entry renders.
  - Each entry's King is resolved via `_king_leader_id()` (Phase 217);
    a kingdom with no `is_king`-flagged leader recorded falls back to
    its own `KingdomState.name` rather than guessing a King's name.
  - Non-breaking: full suite passed unchanged (2620 passed) before any
    new tests were written, after updating 2 pre-existing
    `compose_letter_report()` tests (Phase 215/217) whose expected
    output now needs the always-present DIPLOMACY section inserted --
    a mechanical update, not a behavior change. 6 new tests added
    (2626 passed total) in `tests/test_turn_report.py`, covering:
    no-other-kingdoms all-empty state, an unallied kingdom listed as
    Neutral, an allied kingdom listed as Allied, AT WAR always
    rendering empty regardless of allegiance state, the no-King-
    recorded fallback to `KingdomState.name`, and multiple kingdoms
    sorted by kingdom id.
- **Phase 219**: `report/turn_report.py
  describe_finances_report()` (new) -- the "FINANCES" section, wired
  into `compose_letter_report()` between DIPLOMACY and ARMIES
  (matching the real letter's own relative order, skipping the still-
  unwired PROVINCES/CHARACTERS that sit between FINANCES and ARMIES in
  a real letter).
  - **Only one real line renders**: `"Gold in treasury"` (real
    `Rep_Econ`'s own `lgold[kng]`, directly `KingdomState.treasury`).
    Every other real `Rep_Econ` line is confirmed absent, not merely
    unpopulated: "Expected Revenues" needs `Tax_Base(kng)`, "Expected
    Expenses" needs `ACost`/`LCost` summed across every army/leader
    this kingdom pays for (both confirmed absent from every available
    `.PAS` file, the same citation `describe_armies_report()`'s own
    docstring and `plan_dispatch.py`'s Phase 158 note already
    established), the optional "+Invention Bonus" line needs
    `Inv_Bonus(kng)` derived from held Discoveries, and the optional
    Evilking/ThiefPrince notes need office-holder tracking (the same
    IMPERIAL OFFICE REPORT gap `compose_letter_report()`'s own
    docstring already names).
  - **The Discoveries of the Sages list always renders empty**: no
    per-kingdom Discovery-tracking field exists anywhere in this
    project -- `models/discovery.py`'s own `Discovery` enum and
    `DISCOVERY_NAME`/effect-magnitude tables (Phase 91/135) model the
    *vocabulary* only, never a "kingdom X holds discovery Y" record.
    Confirmed absent, so the real, sourced `"None at present"` string
    always renders here instead of a guess at zero discoveries.
  - Sourced verbatim (`Rep_Econ`, `~REPORTS.PAS` line 272-320): the
    section header, the opening sentence (rejoined across its own 2
    raw `WRITELN` lines, same convention as `_ARMIES_REPORT_OPENING`),
    the "Gold in treasury:" label, and the Discoveries intro sentence.
  - Non-breaking: full suite passed unchanged (2626 passed) before any
    new tests were written, after updating 2 pre-existing
    `compose_letter_report()` tests (Phase 215/217/218) whose expected
    output now needs the always-present FINANCES section inserted --
    a mechanical update, not a behavior change. 4 new tests added
    (2630 passed total) in `tests/test_turn_report.py`, covering: a
    non-zero treasury figure, a zero treasury figure, the Discoveries
    list always rendering "None at present", and reading only the
    given kingdom's own treasury (not another kingdom's).
- **Phase 220**: `report/turn_report.py
  describe_provinces_report()` (new) -- the "PROVINCES" section,
  sourced from `Rep_Provs` (`~REPORTS.PAS` line 404-450), wired into
  `compose_letter_report()` between FINANCES and ARMIES (matching the
  real letter's own relative order, skipping the still-unwired
  CHARACTERS that sits between PROVINCES and ARMIES in a real letter).
  - **Rendered, one readable line per owned province** (not the real
    fixed-width columns -- the same documented choice
    `describe_armies_report()`/`describe_adventure_report()` already
    made): province name (or a `(x, y)` coordinate fallback, the same
    convention `describe_armies_report()` uses for an unnamed
    province), race (`RACE_NAME`), terrain (new `models/map.py
    TERRAIN_NAME` dict, sourced from `CTBOTH.PAS`'s own `tername`
    array at ~line 1219 -- not the *other*, unrelated `tername` at
    ~line 973, which belongs to a Russian-localization-only terrain
    scheme), and percent explored (`ProvinceState.explored_percent`,
    the real `pex[px,py]`'s own per-province, not per-kingdom, scalar).
    Terrain is read via `effective_terrain()` (Part Sea/Flood-aware)
    rather than `illusory_terrain`, which only deceives *outside*
    observers and must never leak into a kingdom's own report of its
    own land. Provinces are sorted by coordinate.
  - **The real Tax column and its whole tax-tier-grouping structure are
    confirmed absent, not merely unwired**: `ptax[px,py]` (the base
    per-province tax value the real table groups and sorts by) is
    never computed anywhere in the available `.PAS` archive -- the
    only other reference (`RUMORS.PAS` line 2140) reads it, never sets
    it -- confirming it's baked into the map at world-generation time
    by the lost `AKGEN.EXE`, the same "world-gen-only, no runtime
    formula" category `ProvinceState.name`'s own `pname` was in before
    Phase 150. Unlike `name`, no bridge in this project ever populates
    a province's tax, so no field was added for it and the column is
    left out entirely.
  - **The real Recruiting-Types columns and the Island parenthetical
    are also confirmed absent**: both depend on `Mod_PAT(px,py,0/1)`
    (the two `ArmyType`s recruitable in a province) and `pt2` (a
    second terrain type marking an island), and neither function nor
    array is defined anywhere in the available Pascal archive. `turn/
    recruit.py is_army_type_compatible_with_race()` answers a
    *different* question (can this army type be recruited here at
    all, given race) than "which exactly two types does this table
    cell name."
  - Non-breaking: full suite passed unchanged (2630 passed) before any
    new tests were written, after fixing the `_armies_state()` test
    helper (it passed `terrain=None` positionally, never read by any
    composer until this phase's `effective_terrain()` call) and
    updating 2 pre-existing `compose_letter_report()` tests (Phase
    215/217/218/219) whose expected output now needs the always-
    present PROVINCES section inserted -- mechanical updates, not
    behavior changes. 6 new tests added in `tests/test_turn_report.py`
    (covering: an owned province's rendered line, the no-provinces-
    owned fallback, ignoring other kingdoms' provinces, the unnamed-
    province coordinate fallback, coordinate sort order, and
    `effective_terrain()` vs. `illusory_terrain` precedence) plus 2 new
    tests in `tests/test_models.py` for `TERRAIN_NAME` (full-coverage
    of every `Terrain` member, and the exact sourced display strings) --
    2638 passed total.
- **Phase 221**: `report/turn_report.py
  describe_characters_report()` (new) -- the "CHARACTERS" section,
  sourced from `Rep_Leaders` (`~REPORTS.PAS` line 658-855, one of the
  largest procedures in the archive, as already flagged by this file's
  own prior notes), wired into `compose_letter_report()` between
  PROVINCES and ARMIES (matching the real letter's own relative order).
  - **Only the real procedure's "impulse 1" pass is modeled**: a
    kingdom's own leaders (`LeaderState.kingdom_id == kingdom_id`) --
    the one pass with genuinely full character data. The real
    procedure's other two passes (wandering Heroes/other Kings' known
    leaders; leaders a Priest-office-holding King can locate via
    clairvoyance) both need data this project doesn't model
    (`Known_Loc` tracking, the Priest office itself -- the same
    IMPERIAL OFFICE REPORT gap) and aren't attempted.
  - **Rendered, one readable two-line entry per owned leader**: name,
    province location (or coordinate fallback), Alignment
    (`LeaderState.alignment.value`, already the real Pascal `outname`
    string), Temperament (`TEMPER_NAME`), Race (`LeaderState.race` if
    set, else the kingdom's own race -- the real, general-case
    fallback per that field's own docstring), and a second line listing
    skill level for all 15 `Ability` members via new `models/enums.py
    ABILITY_ABBREVIATION` (sourced verbatim from this same procedure's
    own column header, `"TaMaNaArMe WhNeElPsIl DrThExSpSa"`) and
    `SkillTable.pair_for_ability(ability)[0]` (0 if `LeaderState.skills`
    is `None`). A leader with no recorded Alignment/Temperament renders
    "Unknown" -- a documented placeholder for genuinely missing data
    (this project's own "None = not recorded" convention allows a gap
    the real `lalign`/`ltemper` arrays never have).
  - **Confirmed absent, not merely unwired**: Pay (`LCost`, same
    citation as `describe_armies_report()`'s own gap); Gender (no
    `Gender()` concept exists anywhere in this project); the
    Discovery-based skill-modifier row (`dknow`-driven `^`/`^^`
    markers, same gap as FINANCES' own empty Discoveries list);
    magic-item-ownership tick marks and the per-leader treasure list
    (`NT_Owned`/`List_Treas`) -- left out of this phase's scope even
    though Phase 140's item-ownership registry could in principle
    answer part of it, matching every other section's own "readable
    line, not the full real table" precedent.
  - Non-breaking: full suite passed unchanged (2638 passed) before any
    new tests were written, after updating 2 pre-existing
    `compose_letter_report()` tests (Phase 215/217/218/219/220) whose
    expected output now needs the always-present CHARACTERS section
    inserted -- mechanical updates, not behavior changes. 7 new tests
    added in `tests/test_turn_report.py` (covering: an owned leader
    with no recorded data, the no-leaders-owned fallback, ignoring
    other kingdoms' leaders, the unnamed-province coordinate fallback,
    recorded Alignment/Temperament/Race rendering, recorded skill
    levels, and leader-id sort order) plus 2 new tests in
    `tests/test_models.py` for `ABILITY_ABBREVIATION` (full coverage of
    every `Ability` member, and the exact sourced abbreviations) --
    2647 passed total.
- **Phase 222**: `parser/gw_world.py parse_gw_world()` (new) --
  a parser for the original engine's "world file" format (e.g. `GW3`,
  `GW3__T1`), the first step of a much larger arc the user is walking
  through by hand: unblocking IMPERIAL OFFICE REPORT's own confirmed
  permanent dead end (`models/office.py`'s own Phase 137 docstring) by
  supplying real rulebook material -- the "TABELLA DELLE CARICHE
  IMPERIALI" (the 8 real Imperial Office merit-point formulas), the
  "TABELLA DEGLI ALLINEAMENTI" (the real `outred[]` Alignment-reduction
  percentages this project's own `REPORTS.PAS` reading had found but
  never had values for), and the real Emperor-election voting rule
  (55%/50% thresholds -- **not** the different 2%/4% strings found in
  `AKGEN.EXE`, which the user explicitly confirmed are not the real
  rule) -- plus asking for `AKGEN.EXE`/the real `GW*` world files to be
  checked for corroboration. Almost every one of those formulas needs a
  real per-province tax value (`ptax`/"Tax_Base"), confirmed absent
  since Phase 158 and reconfirmed at every section composer since
  (FINANCES, PROVINCES) -- this phase closes that gap for good, by
  parsing it directly out of real world-file data instead of deriving
  it from a formula (none survives).
  - **No surviving Pascal source declares this file's format** -- it
    was recovered empirically by cross-referencing known real per-
    province Tax/Race/Terrain values quoted verbatim in a real King's
    own turn-report letter (`SE3__T1.K2`'s "PROVINCES" section and its
    own ASCII map legend) against the raw integers in the matching real
    world-file snapshot (`GW3__T1`, same game, same turn). See
    `parser/gw_world.py`'s own module docstring for the full recovery
    with quoted evidence.
  - **Confirmed record shape**: 4 lines per province (162 total,
    confirmed twice -- a file-wide regex match count, and a clean
    remainder-free line-count division) -- name, `"<tax> <terrain> 0
    <race> 0 6"`, an undecoded 2-integer line, and a governing leader's
    own id (`255` = unowned). `terrain`/`race` are the *exact* ordinal
    values this project's own `Terrain`/`Race` enums already use --
    confirmed across 20+ real records, no new mapping table needed.
  - **A real naming correction made mid-phase**: the trailing id was
    first assumed to be an owning kingdom id (matching the research
    agent's own initial framing); cross-checking `SE3__T1.K2`'s own map
    legend (`"Philo(70)"` governing Transylvania -- Philo is a Hero, not
    a King) proved it's actually the *governing leader's own id*, not a
    kingdom id -- `GWProvinceRecord.governor_leader_id`, not
    `owner_kingdom_id`. For a King-governed province this id happens to
    equal the kingdom id (the same project-wide "King's leader_id ==
    kingdom_id" convention), but resolving it in general needs a
    `GameState`-level leader/kingdom lookup this pure file parser
    deliberately doesn't perform.
  - **A bonus discovery, not consumed by this parser**: the same map
    legend also prints each province's own real coordinate as
    `"<Name>(<XXYY>)"` (e.g. `"Macondo(0205)"`) -- cross-referencing the
    letter's own row layout against `GW3__T1`'s own on-disk record order
    strongly suggests row-major ordering, a promising lead for a future
    phase's coordinate-bridging work, not implemented here.
  - **Known gaps, deliberately not attempted this phase**: no
    coordinate field exists in a province's own record, so
    `parse_gw_world()` returns file-order records, not `HexCoord`-keyed
    `ProvinceState`s -- bridging into `GameState.provinces` is deferred.
    The undecoded 2-integer middle line, `governor_leader_id`-to-
    kingdom resolution, and everything outside the province-record block
    (kingdom headers, a differently-shaped record format after the
    block) are all out of scope here too.
  - New fixture: `tests/fixtures/world/G3/GW3__T1` (44KB, real,
    user-provided, read-only reference data -- the same precedent
    `tests/fixtures/reports/G6/` already established).
  - Non-breaking: full suite passed unchanged (2647 passed) before any
    new tests were written (this phase adds a wholly new, previously
    untouched module -- no existing call site could regress). 6 new
    tests added in `tests/test_gw_world_parser.py` (covering: the full
    162-province count, exact Tax/Race/Terrain match against real
    letter-quoted ground truth for 3 provinces, the `255`-unowned-to-
    `None` sentinel, a King's own capital resolving to his own id,
    3 more Race ordinals cross-checked, and a truncated-record parse
    error) -- 2653 passed total.
- **Phase 223**: `parser/gw_world_bridge.py
  bridge_gw_world_provinces()` (new) -- bridges `GWProvinceRecord`s into
  real `HexCoord`-keyed `ProvinceState`s, closing Phase 222's own
  "no coordinate field" known gap. Also adds `ProvinceState.tax: int |
  None = None` (`models/game_state.py`), the real `ptax[px,py]` this
  project has needed since Phase 220's own `describe_provinces_report()`
  gap.
  - **The coordinate mapping is empirically confirmed, not a lead
    anymore**: collected every `(name, x, y)` triple findable across all
    9 of game 3's real turn-1 letters' own ASCII map legends (`"<Name>
    (<XXYY>)"`, e.g. `"Macondo(0205)"`), checked all 63 matchable names
    against their own position in `GW3__T1`'s on-disk record order, and
    got a **100% exact match, zero mismatches**, under: `x (1-indexed) =
    index // 9 + 1`, `y (1-indexed) = index % 9 + 1` -- i.e. the file's
    own record order is column-major (18 x-values outer, 9 y-values
    inner, 18 x 9 = 162), mirroring `REPORTS.PAS Rep_Provs`'s own real
    iteration order verbatim. Converts directly to this project's own
    0-indexed `HexCoord(index // 9, index % 9)`, no offset arithmetic.
  - **Deliberately not attempted**: `GWProvinceRecord.
    governor_leader_id` is not resolved to an owning kingdom id here (a
    `GameState`-level leader/kingdom lookup this pure bridging function
    doesn't have) -- every bridged `ProvinceState.owner_kingdom_id` is
    `None`. The 18x9 board size is confirmed for this one real fixture
    (`GW3__T1`), not cross-checked against a second world file -- a
    `height` parameter is exposed rather than hardcoded as universal.
  - Non-breaking: full suite passed unchanged (2653 passed) before any
    new tests were written (both the new bridge module and the new
    `ProvinceState.tax` field are additive, no existing call site
    reads either). 5 new tests added in `tests/test_gw_world_bridge.py`
    (covering: the full 162-province bridge, Macondo's exact confirmed
    coordinate + Tax/Race/Terrain, the origin province, `owner_kingdom_id`
    always `None`, and a not-a-multiple-of-height `ValueError`) plus
    2 new tests in `tests/test_game_state.py` for `ProvinceState.tax`
    (default `None`, and settable) -- 2660 passed total.
- **Phase 224**: `parser/gw_world_bridge.py
  resolve_province_owners()` (new) -- resolves Phase 223's own
  deliberately-deferred `GWProvinceRecord.governor_leader_id` into a
  real `ProvinceState.owner_kingdom_id`, via a `GameState` whose
  `leaders` dict is already populated (e.g. `turn/kingdom_bridge.py
  sync_leaders_from_kingdom()`).
  - A King-governed province resolves directly (the King's own
    `leader_id` equals his `kingdom_id`, the project-wide convention);
    a Hero-governed province resolves via that Hero's own `LeaderState.
    kingdom_id` (verified against the real "Philo(70)" cross-check --
    Philo governs Transylvania, and a synthetic `LeaderState(leader_id=
    70, kingdom_id=6, ...)` correctly resolves Transylvania's owner to
    kingdom 6). An independent Hero (no kingdom) resolves to `None`
    legitimately; a governor id absent from `state.leaders` (e.g. a
    partially-bridged `GameState` missing that kingdom's own move file)
    is left unresolved, not an error -- `resolve_province_owners()`
    mutates `provinces` in place and returns the count of governors it
    actually found in `state.leaders`.
  - Non-breaking: full suite passed unchanged (2660 passed) before any
    new tests were written (a wholly new function, no existing call
    site reads it). 4 new tests added in `tests/test_gw_world_bridge.py`
    (covering: a King's own capital resolving directly, a Hero-governed
    province resolving to his own kingdom, unresolved governors staying
    `None` with a partially-bridged `GameState`, and an independent
    Hero resolving to `None`) -- 2664 passed total.
- **Phase 225**: `turn/tax_base.py` (new) -- `Tax_Base(kng)`
  aggregation, the FINANCES section's own "Expected Revenues" gap
  (`describe_finances_report()`'s own docstring, confirmed absent from
  every available `.PAS` file, same citation as `ACost`/`LCost`/
  `Inv_Bonus`). Phases 222-224 already recovered the missing input --
  a real per-province base tax (`ProvinceState.tax`) and its real owning
  kingdom (`owner_kingdom_id`) -- so what was left wasn't a data gap, it
  was a summing formula, which is **project-original, not transcribed**
  (flagged per the project's own standing rule for confirmed-absent
  design choices, since no `.PAS` file ever defines `Tax_Base` itself).
  - `province_tax_yield()` combines a province's real base `tax` with two
    fields that already existed with **no consumer anywhere before this
    phase** (their own docstrings said so): `scar_terrain_gold_reduction`
    (Scar Terrain's cumulative, permanent -2 gold) is subtracted first
    and floored at 0 gold; then `tax_modifier_percent` (Bless +60% /
    Earthquake -100%, "for one turn," a set not an add) is applied
    (`base * (100 + pct) / 100`, integer division) and floored at 0
    again. Permanent damage before the turn's temporary modifier is the
    natural reading of "permanently" vs. "for one turn" -- no source
    orders the two explicitly.
  - `compute_tax_base(state, kingdom_id)` sums `province_tax_yield()`
    across every province this kingdom (not its allies -- `Tax_Base` is
    real Pascal terminology for one kingdom's own revenue, unlike
    `GameState.friendly_provinces_for()`'s broader owned-or-allied
    military scope) owns with a *known* base tax. A province whose `tax`
    was never bridged from a real `GW3` file contributes nothing and
    isn't counted as 0 -- the same "no data isn't a true zero" stance
    `turn/aspy_execution.py`'s own docstring already took for this exact
    gap.
  - Non-breaking: full suite passed unchanged (2664 passed) before any
    new tests were written (a wholly new module, no existing call site
    reads it). 11 new tests added in `tests/test_tax_base.py` (covering:
    unrecorded tax, plain base tax, Scar Terrain reduction + its floor,
    Bless's bonus, Earthquake's zeroing, the scar-then-Bless combination,
    summing only owned provinces with known tax, ignoring unowned and
    allied-but-not-owned provinces, and a kingdom with no provinces) --
    2675 passed total.
- **Phase 226**: `report/turn_report.py describe_finances_report()`
  now renders the real "Expected Revenues" line (`REPORTS.PAS` line 319,
  confirmed verbatim: `'  Expected Revenues: ',Tax_Base(kng):3`), calling
  Phase 225's `turn/tax_base.py compute_tax_base()` -- the one FINANCES
  line this project could close given the real per-province tax data
  Phases 222-224 recovered. "Expected Expenses" (needs `ACost`/`LCost`,
  still confirmed absent with no per-army/per-leader upkeep data to
  aggregate instead) is unaffected and still doesn't render.
  - Non-breaking: full suite passed unchanged (2675 passed) before any
    new test was written -- the 4 pre-existing exact-line-list assertions
    that already enumerated `describe_finances_report()`'s/
    `compose_letter_report()`'s full output needed a one-line update each
    (inserting the new `"Expected Revenues: 0"` line at its real position)
    to keep matching the now-longer real output; no other existing test
    changed. 1 new test added in `tests/test_turn_report.py`
    (`test_describe_finances_report_expected_revenues_uses_compute_tax_
    base`, confirming only this kingdom's own owned provinces' tax is
    summed, not another kingdom's) -- 2676 passed total.
- **Phase 227**: `turn/merit_points.py` (new) -- the 8 Imperial
  Office Merit Point formulas, closing the formula half of Phase 137's
  own "confirmed, permanent dead end" (that dead end was specifically
  about `REPORTS.PAS Ofc_Pts`'s own missing Pascal globals, which are
  still lost). The user supplied the rulebook's own printed "TABELLA
  DELLE CARICHE IMPERIALI" (page 51, studied directly) -- a different,
  real, sourced description of the same 8 formulas, not a Pascal
  transcription. The table's own 20%/10%x7 Victory Point quotas already
  matched `models/office.py OFFICE_VALUE` exactly, independent
  cross-confirmation the two sources describe the same system.
  - Fully live now (real `GameState` data, no new tracking needed):
    Emperor (reuses Phase 225's `compute_tax_base()` directly),
    Treasurer (`KingdomState.treasury`, confirming Phase 137's own
    speculation), the skill-level terms for Chancellor/Priest/Mage/
    Admiral, Mage's owned-Spell-Wand count, and Admiral's per-kingdom
    "rich sea province" bonus (footnote 1: applies identically to every
    leader of that kingdom, not just whoever found the province).
  - New `models/game_state.py MeritTally` dataclass (`LeaderState.
    merit_tally`) holds the raw, uninc­remented counters the remaining
    terms need (land/naval battle won/lost units, monster HP defeated/
    neutralized, Resurrection/Bless cast count, discovery-first
    attribution) -- the same "field exists, no populating consumer yet"
    convention as Phase 59's own `tax_modifier_percent` (only wired up
    166+ phases later). No battle/encounter/cast call site increments
    these yet; a future wiring phase.
  - `legendary_item_victory_point_bonus_count()`: the table's own
    closing "10 restanti Punti Merito" paragraph (10 named artifacts,
    flat Victory Point share, explicitly *not* an 8-office Rank contest
    and *not* reduced by Alignment-vs-Emperor distance) -- all 10 names
    cross-checked 1:1 against this project's own pre-existing
    `models/treasure.py TREASURE_NAME` with zero mismatches.
  - `merit_point_tiebreak_key()`: footnote 3's treasury-then-tax-base
    tie-break, both Kingdom-scoped; an independent Hero (no Kingdom)
    falls back to `(0, 0)`, a documented gap.
  - Non-breaking: full suite passed unchanged (2676 passed) before any
    new tests were written (2 wholly new modules/fields, no existing
    call site reads them). 18 new tests added (16 in `tests/
    test_merit_points.py`, 2 in `tests/test_game_state.py` for
    `MeritTally`'s all-zero default and per-leader independence) --
    2694 passed total.
- **Phase 228**: `turn/emperor_election.py` (new) -- the
  Emperor election mechanic, rulebook [10.2] (the rulebook's own words:
  this is literally "cosa si deve fare per mettere fine a una partita",
  what must be done to end a game). Standing instruction respected: the
  55%/50% thresholds below are the confirmed real rule; the 2%/4%
  strings found in `AKGEN.EXE` are confirmed NOT the real rule and are
  not used.
  - `can_request_election()`: a single King or an "alleanza di Re" (one
    connected component of `GameState.allied_kingdoms`) qualifies once
    their combined `Tax_Base` (Phase 225) exceeds 55% of every kingdom's
    `Tax_Base` summed. The rulebook's own "non è possibile tenere
    votazioni per due turni consecutivi" ban is enforced via the new
    `GameState.last_emperor_vote_turn`.
  - `tally_emperor_vote()`/`resolve_emperor_election()`: `{voter_kingdom_
    id: candidate_kingdom_id}` ballots, each weighted by that voter's own
    `Tax_Base` at the voting turn; a candidate needs a strict majority
    (>50%) of votes actually *cast* (an abstention isn't a vote for
    nobody). `resolve_emperor_election()` records the outcome onto the
    new `GameState.emperor_kingdom_id` -- a failed/no-quorum vote never
    clears a still-standing previous Emperor, only `last_emperor_vote_
    turn` always advances.
  - `alignment_victory_point_reduction_percent()`: the rulebook's own
    post-election paragraph -- every King's Victory Points drop by a
    percentage proportional to their Alignment's ordinal distance
    (`models/alignment.py ALIGNMENT_ORDINAL`, the same real Pascal
    sequence `turn/hire_pay.py` already established as load-bearing for
    an identical distance formula) from the new Emperor's Alignment,
    using the user-supplied "TABELLA ALLINEAMENTI" reduction-per-step
    column (7 of 10 `Alignment` members; Anti-Holy/Mechanical/Special a
    confirmed gap). Reproduces the rulebook's own worked example exactly
    (Pagan, 15%/step, distance 3 from Good -> 45%).
  - **Explicitly out of scope**: determining the game's total available
    Victory Points and attributing the other 7 Imperial Offices (needs
    the full Merit Point Rank contest across every leader in the game,
    Phase 227's own `merit_point_tiebreak_key()` included) -- a
    separate, considerably larger follow-up.
  - **Not decoded**: the "RICHIEDERE UNA VOTAZIONE" (Call for Vote) plan
    action itself [1.3] -- no real `AK3__T*.K1` sample with this action
    has been seen, the same "mechanic before the plan-file wiring" order
    already used for `turn/tax_base.py`.
  - Non-breaking: full suite passed unchanged (2694 passed) before any
    new tests were written (a wholly new module + 2 new `GameState`
    fields, no existing call site reads them). 16 new tests added (15 in
    `tests/test_emperor_election.py`, 1 in `tests/test_game_state.py`
    for the two new fields' `None` defaults) -- 2710 passed total.
- **Phase 229**: `report/turn_report.py describe_alignment_
  victory_point_reduction()` (new) -- surfaces Phase 228's rulebook
  [10.2] Alignment-distance Victory Point reduction inside the turn
  report, as a new `ALIGNMENT REDUCTION` section appended after
  ADVENTURE in `compose_letter_report()`.
  - **The section itself is project-original, not a Pascal
    transcription** -- `REPORTS.PAS`'s own "Final Standings" block
    (~line 1665-1784) computes this reduction directly into each King's
    own per-King standings row; the real engine never renders it as its
    own separate, labeled table. The *formula and its numeric values*
    are fully real and sourced (rulebook [10.2] + the user-supplied
    "TABELLA ALLINEAMENTI"); only the choice to surface it as its own
    standalone section -- rather than leaving it buried inside the
    still-unbuilt Final Standings table, which needs the full Merit
    Point Rank contest across every leader in the game -- is this
    project's own design, clearly flagged per the project's standing
    rule for unsourced presentation choices.
  - One line per `Alignment` the rulebook's own reduction-per-step
    column covers (7 of 10, ordered by the real Pascal `ALIGNMENT_
    ORDINAL` sequence), each showing that Alignment's own reduction
    percent relative to the newly-elected Emperor's Alignment.
    Anti-Holy/Mechanical/Special are silently skipped (a confirmed
    table gap, not a guessed 0%).
  - Renders (and is included in `compose_letter_report()`) only once
    `GameState.emperor_kingdom_id` is set -- empty/omitted before any
    Emperor election, the same "no header with no body" convention
    every other section here already uses.
  - Non-breaking: full suite passed unchanged (2710 passed) before any
    new tests were written (`emperor_kingdom_id` defaults to `None`, so
    every pre-existing exact-line-list `compose_letter_report()`
    assertion was unaffected). 5 new tests added to `tests/
    test_turn_report.py` (covering: empty before any election, every
    covered Alignment listed with the right reduction, reproducing the
    rulebook's own Pagan/Good worked example, and the section's
    inclusion/omission in `compose_letter_report()`) -- 2715 passed
    total.
- **Phase 230**: `turn/office_holder.py` (new) -- the office-
  HOLDER resolution Phase 227/228 both explicitly deferred ("needs the
  full Merit Point Rank contest across every leader in the game"), plus
  the real `IMPERIAL OFFICE REPORT` section this project has skipped
  since Phase 221 (`compose_letter_report()`'s own docstring: "needs
  office-holder-per-kingdom data no `GameState` field tracks"). Now 9 of
  the real letter's 10 sections are wired (only GENERAL INTELLIGENCE
  REPORT remains).
  - `resolve_office_holder()`/`resolve_all_office_holders()`: Emperor is
    resolved by reading the real election result (`GameState.
    emperor_kingdom_id`, Phase 228) directly, not a Merit Point
    comparison. The other 7 offices are a genuine Rank contest across
    every leader in the game (rulebook [10.1]: "Anche un Eroe può
    aggiudicarsi una carica") -- each leader's own Merit Points come
    from Phase 227's `turn/merit_points.py` formulas, gated by
    `models/office.py OFFICE_MIN_POINTS` (real Pascal `minpts`,
    Phase 81) and tied via `merit_point_tiebreak_key()` (rulebook
    footnote 3).
  - `report/turn_report.py describe_imperial_office_report()`: one
    readable line per office (`models/office.py OFFICE_NAME`, the real
    `ofcname` string) -- not the real procedure's own fixed-width/
    percentage-vs-runner-up columns, the same "readable line" precedent
    every other section here uses. Unlike every other section, it takes
    no `kingdom_id` -- the real procedure loops over every leader in the
    game, so the content is identical across every King's own report.
    Wired into `compose_letter_report()` between ARMIES and ADVENTURE,
    matching the real section order.
  - Non-breaking: full suite passed unchanged (2715 passed) before any
    new tests were written for the new module; wiring the new section
    into `compose_letter_report()` did require updating the 2
    pre-existing exact-line-list assertions that already enumerated its
    full output (inserting the new 9-line block at its real position),
    the same mechanical fix Phase 226/229 already established -- no
    other existing test changed. 13 new tests added (9 in `tests/
    test_office_holder.py`, 4 in `tests/test_turn_report.py`) -- 2728
    passed total.

- **Phase 231**: GENERAL INTELLIGENCE REPORT -- the last of
  the real letter's 10 sections, closing the gap Phase 230 left open.
  Research first confirmed a prior phase's own assumption was wrong:
  `describe_aspy()`/`describe_trail_intelligence()` are already fully
  consumed inside `describe_letter_reports()`, not free raw material for
  this section. Real content, confirmed directly from ~15 real
  `SE3__T*.K*` fixture files: a cross-kingdom world-news feed, one
  `Kingdom of <Name> (#<id>):` block per foreign kingdom whose activity
  this reader can see, each followed by that kingdom's own narrative
  lines. No `Rep_Intel`-equivalent procedure survives anywhere in the
  `.PAS` archive (only `Rep_Allies`/`Rep_Econ`/`Rep_Provs`/
  `Rep_Leaders`/`Rep_Armies` exist) -- the same "the caller is lost, not
  the callees" situation as `turn/movement.py`'s own hex adjacency
  scheme. Presented three honestly-scoped options to the user (document
  the gap and stop / minimal slice / build the full system); the user
  chose the full system.
  - `models/game_state.py WorldEvent` (new dataclass) + `GameState.
    world_events`/`record_world_event()`: a turn-global, cross-kingdom
    event log -- confirmed absent from `GameState` entirely before this
    phase (no battle-occurrence log, no ownership-change history).
  - `turn/world_events.py` (new): `is_visible_to()`, the rulebook [1.4]
    visibility rule ("un giocatore viene informato quando una provincia
    adiacente al suo Reame cambia di mano e può anche ricevere
    informazioni sulle attività di personaggi controllati da un altro Re
    quando agiscono entro i confini del suo Reame") read as one test: a
    province this kingdom owns, or one adjacent to it.
  - `turn/battle_orchestrator.py BattleReport` gained 3 new fields
    (`province_coord`/`attacker_kingdom_id`/`defender_kingdom_id`), all
    populated in `fight_battle()` from values it already computes
    locally -- the only way a caller several layers away can recover
    which two kingdoms fought and where.
  - `report/turn_report.py record_battle_world_events()` (new): scans a
    turn's own `list[PhaseDispatchResult]` for every reachable
    `BattleReport` (duck-typed across the three real shapes a battle can
    surface in -- direct, `.battle_report`, or `.battle.report` --
    matching `turn_processor.py`'s own four real call sites) and records
    just the battle-winner sentence (`render_battle_winner()`) as a
    `WorldEvent`. **Deliberately narrow**: real letters also show
    movement, plagues, terrain illusions, and cast-spell narrations, all
    confirmed real and explicitly deferred -- this phase wires the one
    event type (battle results) this project already has a full
    narrative renderer for, matching the real fixtures' own richest,
    first example (`SE3__T2.K2` line 506, Circe invading Big Sky). The
    fuller per-column clash narrative (`describe_battle()`'s own
    `army_names` parameter) stays out of scope -- this project has no
    army-naming system wired into any real call site yet, a separate,
    already-documented gap.
  - `report/turn_report.py describe_general_intelligence_report()`
    (new): groups every visible `WorldEvent` by its own province's
    *current* `owner_kingdom_id` (read fresh at render time, not stored
    on the event) -- confirmed against real fixture text where a
    battle's own province files under the post-battle winner's name, and
    a back-and-forth province's whole news thread files under whoever
    owns it by the end (`SE3__T2.K2`'s Circe/Big Sky and `SE3__T11.K6`'s
    Rejaf tug-of-war). Reuses `_diplomacy_entry()` (Phase 218) for the
    `"Name (#id)"` formatting. Wired into `compose_letter_report()` as
    the 10th and final real section, right after ADVENTURE -- **but
    only after a caller has already run `record_battle_world_events()`
    once for the whole turn**, since world events are turn-global, not
    per-King (calling it once per `compose_letter_report()` call would
    duplicate every entry once per King).
  - Non-breaking: full suite passed unchanged (2728 passed) before any
    new tests were written; wiring the new section into
    `compose_letter_report()` did require updating the 2 pre-existing
    exact-line-list assertions that already enumerated its full output
    (appending the new 2-line block at the real position), the same
    mechanical fix every prior section-adding phase has needed. 20 new
    tests added (`tests/test_world_events.py` new, 5 tests; `tests/
    test_game_state.py` +3; `tests/test_battle_orchestrator.py` +1;
    `tests/test_turn_report.py` +11) -- 2747 passed total.

- **Phase 232**: two more real GENERAL INTELLIGENCE REPORT
  event sources -- Plague and Illusory Terrain casts -- on the user's
  own explicit request to develop "movimenti, pestilenze, incantesimi"
  (movement, plagues, spells). Research corrected a prior-phase
  assumption along the way: Phase 231's own docstring had claimed "this
  project has no plague mechanic modeled anywhere at all," but grepping
  the Pascal archive for "plague" found it fully implemented already
  (`Spell.PLAGUE`, `turn/cast_execution.py _execute_plague()`, wired
  through `plan_dispatch.py` since Phase 59) -- the gap was never the
  mechanic, only GIR's own recording of it.
  - Reading `SAY.PAS` directly (not just `REPORTS.PAS`) surfaced a real,
    previously-unseen distinction: every `Say(...)` call carries a
    `spytype` severity tag (`S_Comm`, `S_PCom`, `S_AA`, `S_Batt`, ...).
    `_SPlague: Say('@ was hit by a plague.',S_Comm)` and `_STerIl:
    Say(Concat('the ',tername[...],' terrain of @ was magically made to
    appear as \`.'),S_Comm)` are real, "commonly known" (`S_Comm`)
    province-wide notices, textually distinct from and additional to
    `SPELL_CAST_ANNOUNCEMENT[Spell.PLAGUE]`/`[Spell.ILLUS_TERRAIN]` (the
    caster's own private, army-list-carrying first-person announcement
    `describe_cast()` already renders into the caster's own LETTER
    REPORTS entry). `_SPlague`'s own wording matches a real fixture
    verbatim (`SE3__T1.K8`: "Transylvania was hit by a plague.").
    `spytype` itself turned out to be a text-rendering severity marker
    (feeding `report/prose.py render()`-style word-choice branches, not
    a "which kingdoms receive this" recipient list) -- the real
    broadcast-decision logic itself is still confirmed lost with the
    main driver, so `turn/world_events.py is_visible_to()`'s own
    rulebook [1.4] adjacency rule (Phase 231) stays the visibility test.
  - `report/turn_report.py render_plague_world_event()`/
    `render_illus_terrain_world_event()` (new) render the two `S_Comm`
    templates; `record_spell_world_events()` (new) scans a turn's own
    `list[PhaseDispatchResult]` for successful Plague/Illusory Terrain
    `CastExecutionResult` entries and records a `WorldEvent` for each --
    the second real event-*source* function alongside Phase 231's
    `record_battle_world_events()`, sharing the same "call once per
    turn before any `compose_letter_report()`" contract.
  - **Movement stays explicitly deferred, with a sharper reason than
    Phase 231 could give**: `render_march()` (Phase 104, MARCH.X) was
    initially assumed to cover it, but its own real templates need a
    `^P` "province number" marker this project has no honest synthesis
    for (`turn/hex_numbering.py encode_hex_number()` encodes a
    *different*, empirically-inferred move-file numbering scheme --
    reusing it for `^P` would silently conflate two unrelated numbering
    systems, a real correctness bug, not a shortcut). MARCH.X's own
    wording ("marched into @ ^P with...") also doesn't textually match
    the real fixtures' own "flew over to"/"flew into" phrasing in the
    first place, so reusing it wouldn't have been an honest transcription
    either way -- not attempted here.
  - Non-breaking: full suite passed unchanged (2747 passed) before any
    new tests were written. 8 new tests added to `tests/
    test_turn_report.py` -- 2755 passed total.

- **Phase 233**: Plague's own spread-to-adjacent-provinces
  mechanic -- rulebook [4.25.3]'s last unmodeled piece, on the user's
  own explicit request ("sviluppa la meccanica di diffusione della
  pestilenza tra province adiacenti"). Closes the exact gap `_execute_
  plague()`'s own Phase 232-era docstring had flagged: "The 15%/phase
  spread to an adjacent province stays unmodeled... a natural
  follow-up, not attempted this phase."
  - `models/game_state.py`: `ProvinceState.plague_active: bool` (new,
    persistent -- never auto-cleared, the rulebook names no "the plague
    dies out" end condition) and `ArmyState.plague_immune: bool` (new)
    -- rulebook: "If a unit survives a plague, it's immunized from
    dying in future plagues (it may instead drop a level in quality.)"
  - `turn/cast_execution.py`: `apply_plague_exposure()` (new, public)
    factors the army-eligibility/destroy/immunity logic out of
    `_execute_plague()` so both the original cast and the new spread
    mechanic share it exactly. `_execute_plague()` itself now sets
    `province.plague_active = True` on a fresh affliction and is a
    no-op beyond `applied=True` on an already-active province --
    "casting more than one Plague spell does not have a cumulative
    effect." `_quality_one_level_down()` (new) implements the "may
    instead drop a level in quality" clause for an already-immune
    army re-exposed -- a flat one-level drop, reusing the *same*
    exposure chance the rulebook gives no separate probability for
    (documented, unsourced choice).
  - `turn/plague_spread.py` (new): `resolve_plague_spread()` snapshots
    every currently-`plague_active` province, then rolls one 15%
    spread attempt per unafflicted neighbor -- a newly-infected
    province never itself spreads within the same call, only "the next
    phase" (a direct reading of the rulebook's own wording as this
    project's own phase-by-phase loop boundary, not a guessed
    rate-limit). Spread exposure uses the base 10% chance with no
    caster-level bonus -- documented, unsourced: no caster exists for a
    natural spread event to draw a level from.
  - `turn/turn_processor.py`: `resolve_plague_spread()` wired into
    `run_turn()`'s own per-phase-boundary dispatch, the same call site
    `_dispatch_contested_rebattles` (Phase 55) already established --
    "the next phase" *is* this project's own phase loop boundary.
    Produces no `PhaseDispatchResult` (not tied to any leader's plan),
    the same category as `_apply_defend_reinforcements`.
  - **Movement (GENERAL INTELLIGENCE REPORT wiring) intentionally left
    untouched this phase** -- the user's own request was scoped to the
    spread mechanic itself, not GIR narration of it; recording newly-
    infected provinces as world events is a natural, separate future
    follow-up (`resolve_plague_spread()` already returns the newly-
    infected coordinates for exactly that purpose).
  - Non-breaking: full suite passed unchanged (2755 passed) before any
    new tests were written. 14 new tests added (`tests/
    test_cast_execution.py` +7, `tests/test_plague_spread.py` new with
    6 tests, `tests/test_turn_processor.py` +1 integration test) --
    2769 passed total.

- **Phase 234**: closes the loop Phase 233 deliberately left
  open -- `resolve_plague_spread()` already returned its own newly-
  infected coordinates "for a future caller to narrate if it chooses";
  this phase is that caller, on the user's own explicit follow-up
  request.
  - `turn/turn_processor.py`: each coordinate `resolve_plague_spread()`
    returns is now wrapped into its own `PhaseDispatchResult`
    (`phase_label="plague-spread"`, `result=`the bare `HexCoord`,
    `leader_id=0`, `segment_index=-1`) -- the exact sentinel convention
    `_dispatch_contested_rebattles` already established for its own
    `"forced-rebattle"` entries not tied to any leader's plan -- so
    `run_turn()`'s own return value carries this the same way it
    already carries battle/cast results for Phase 231/232's own
    recorders.
  - `report/turn_report.py record_plague_spread_world_events()` (new):
    filters `results` for `phase_label == "plague-spread"` and renders
    the *same* real `S_Comm` "@ was hit by a plague." notice
    (`render_plague_world_event()`, Phase 232) a direct cast already
    uses -- the rulebook and the real fixture text draw no distinction
    between a directly-cast and a spread-caused affliction. The third
    real GENERAL INTELLIGENCE REPORT event-source function, alongside
    `record_battle_world_events()` (Phase 231) and
    `record_spell_world_events()` (Phase 232); same "call once per
    turn, before any `compose_letter_report()` call" contract.
  - Non-breaking: full suite passed unchanged (2769 passed) before any
    new tests were written. 3 new tests added to `tests/
    test_turn_report.py`, plus `tests/test_turn_processor.py`'s own
    Phase 233 plague-spread test extended to assert the new
    `PhaseDispatchResult` entries -- 2772 passed total.

- **Phase 235**: the rest of the real `S_Comm` ("commonly
  known") province-effect spells, on the user's own explicit request
  to continue closing GENERAL INTELLIGENCE REPORT's own deliberately-
  narrow event-source list -- specifically asked to revisit Skeletal
  Army as an example candidate.
  - Read every single `S_Comm`-tagged `Say()`/`Sps()` call in `SAY.PAS`
    directly (not just the ones already known), confirming exactly
    which real notices qualify: `_SFlood` (Flood, literal template)
    and, via `PROCEDURE Sps(sp: spell; fam: integer); BEGIN
    FD('c:\tp\prose\spnote.x2',fam,1001+ord(sp)); END;` (dispatches
    through the *same* `SPNOTE.X2` file/index this project's own
    `SPELL_CAST_ANNOUNCEMENT` dict was already extracted from, Phase
    122) -- `_SPart` (Part Sea) and `_SQuake` (Earthquake), both of
    whose real `SPELL_CAST_ANNOUNCEMENT` entries need only a province
    name, confirming they're safe to render standalone (no "< cast a
    spell and" opening clause -- `Sps(...)`'s own real call sites sit
    in a separate dispatch section from the caster's own announcement
    group).
  - **Skeletal Army specifically checked and confirmed *not* eligible**
    -- `_ARises: Sps(Skeletal_Army,S_AA)` is tagged `S_AA` ("kingdom-
    only"), not `S_Comm`; a real, sourced negative result, not an
    oversight. Also true of Tornado (`_STorn`, `S_AA`) and Illusory
    Armies (`_SIllAr`, `S_AA`) -- every other `Sps(...)` dispatch was
    checked and is either `S_AA`, `S_PCom`, `S_Adv`, or `S_Admin`
    (Bless), none confirmed `S_Comm`.
  - `report/turn_report.py`: `render_flood_world_event()`/
    `render_bystander_spell_notice()` (new); `record_spell_world_
    events()` extended to cover `Spell.FLOOD`/`Spell.PART_SEA`/
    `Spell.EARTHQUAKE` alongside Plague/Illusory Terrain (Phase 232) --
    all five spells' own `_execute_*()` functions were already fully
    implemented (Phase 59), so this phase is purely the GIR-recording
    layer, the same "mechanic already existed, only the recording was
    missing" situation Phase 232 already found for Plague itself.
  - Non-breaking: full suite passed unchanged (2772 passed) before any
    new tests were written. 8 new tests added to `tests/
    test_turn_report.py` -- 2780 passed total.

- **Phase 236**: two open-gap items the user chose from a
  status report ("gap ancora aperti": army naming blocking
  `describe_battle()`, and other spells with known formulas but not
  executed) -- "vai col Gap 1, poi riprendi la Fase 209" -- this phase
  is Gap 1 only (the Fase 209 CAST-orchestration resume is separate,
  still-pending follow-up work).
  - Ported `REPORTS.PAS:986-992`'s real Army List table name-column
    builder (`turn/army_naming.py`, new: `make_army_ordinal()` =
    `YAK.PAS Make_Des`'s Moderator/English branch with the real
    11th/12th/13th exception; `make_army_display_name()` = the
    ordinal + `" Skel "` + `atdesig` (Skeletal-Army-raised) / ordinal +
    `atname` (normal) branch) -- verified directly against real letter
    data (`SE3__T0.K1:135,137`: "108th Skel Bowmen" / "110th Bowmen").
    `ArmyState.is_skeletal` (new field) is set by `turn/
    cast_execution.py _execute_skeletal_army()` for every army it
    raises -- the real `Zomboid` `astate` marker this table checks, with
    no real `astate[an]:= Zomboid` assignment site anywhere in the
    extracted source (another "lost with the missing main driver" gap,
    reconstructed from `Zomboid`'s own name + the literal "Skel" text +
    `RUMORS.PAS:354`'s adjacent `Undead` check).
  - **Correction discovered along the way**: `report/turn_report.py`'s
    own module docstring had claimed since early on that no
    ordinal-numbering/naming system exists anywhere in this project
    (citing `LNAMES.PAS`/`PRNAMES.PAS`, which are just name word-lists,
    not naming logic) -- false. `models/army_naming.py make_army_name()`
    (`YAK.PAS Make_AName`) has existed since Phase 149, and was already
    this project's established general-purpose per-army-naming utility
    (Phase 212's own `_army_display_name()`/`_trail_army_name()`) despite
    its own docstring noting its only *directly* confirmed real Pascal
    call site is an Imperial-Office-holder display line for offices this
    project doesn't model. Asked the user whether to extend that same
    precedent to `describe_battle()`; confirmed yes.
  - `report/turn_report.py`: new `build_battle_army_names(state,
    battle_report)` -- synthesizes the `army_names` map for every army
    id in a battle (columns + destroyed/pursued/retreated lists) via
    `make_army_name()`, preferring a still-live `ArmyState`'s own real
    `kingdom_id` for race resolution, falling back to the column's own
    `BattleUnit.army_type` + `BattleReport.attacker_kingdom_id`/
    `defender_kingdom_id` (Phase 231) for an already-destroyed army.
    `describe_battle()`'s own `army_names: dict[int, str]` parameter is
    replaced with `state: GameState`, calling this internally -- no more
    caller-supplied names for armies (province names, still unsourced,
    stay caller-supplied via `destination_names`). Existing `describe_
    battle()` tests updated: `make_army_name()` doesn't prepend "the"
    (unlike the old placeholder test strings), matching its own real,
    sourced output exactly.
  - Non-breaking: full suite passed unchanged (2780 passed) before any
    new tests were written. 16 new tests added (8 in new `tests/
    test_army_list_naming.py`, 4 new `build_battle_army_names()` tests
    plus 3 updated `describe_battle()` tests in `tests/
    test_turn_report.py`, 1 new `is_skeletal` assertion in `tests/
    test_cast_execution.py`) -- 2792 passed total.

- **Phase 237**: closes 2 of the 3 remaining "formula ready,
  never dispatched" secret Personal-Combat spells identified in the
  same Gap 2 status report as Phase 236's own Gap 1 -- Gate Demon and
  Lava Pool, both wired into `turn/search_execution.py
  _resolve_cast_tactic()` the same way Phases 209/210/211 wired every
  other secret spell. (Augur Combat, the third, is closed separately in
  Phase 238 below.) First re-verified that Phases 209/210 --
  the CAST-tactic orchestration engine itself -- were in fact already
  complete and committed, correcting an earlier assumption in this same
  conversation that they were still pending from an old plan-mode draft.
  - **Gate Demon [GD]**: on a successful cast, rolls the summoned demon's
    own species (`models/monster.py roll_gate_demon_type()`) and builds
    it a real `Combatant` via the exact "clone from `MONSTER_COMBAT_
    STATS`, roll `hit_points`" pattern the guardian monster itself
    already uses. The 50% refusal roll (`resolve_gate_demon_refusal()`)
    only fires when the opponent's alignment is Evil-to-Undead
    (`ALIGNMENT_ORDINAL` 5-7) -- a monster opponent has no persisted
    alignment anywhere in this project, so it's rolled fresh via
    `models/monster.py roll_monster_alignment()`, the same real,
    sourced per-species distribution world generation itself uses,
    rather than guessed or left unusable. The demon then fights the
    opponent via a plain `resolve_melee_duel()` (its own real
    spellcasting, confirmed by the `SE3__T11.K1` worked example already
    quoted in `turn/encounter.py`, stays out of scope -- it would need
    this same CAST engine recursively). A win credits the caster
    (`GATE_DEMON_WINNER_RETURNS_TO_ABYSS`); a loss has no direct penalty
    and the plan simply continues (`GATE_DEMON_LOSS_CASTER_RESUMES_
    FIGHT_AT_CURRENT_RANGE`).
  - **Lava Pool [LP]**: a flat, target-speed-keyed escape roll
    (`resolve_lava_pool_escape()`) after an immunity check
    (`models/advanced_ability.py LAVA_POOL_IMMUNE_MONSTERS` -- flying/
    underwater/anti-holy/ghostly species). A monster target's speed
    comes straight from `MONSTER_COMBAT_STATS`; a leader target has no
    sourced speed of its own, so it defaults to `MonsterSpeed.MEDIUM` --
    the same tier `turn/encounter.py`'s own [5.6] Flee quote already
    groups "other characters" into ("medium-speed monsters or other
    characters is a 50-50 proposition"). A failed escape is a full,
    instant kill (`LAVA_POOL_KILLS_INSTANTLY`).
  - `turn/encounter.py`'s own "not wired into `turn/search_execution.py`"
    confessions for both spells corrected to reflect the new wiring.
  - Non-breaking: full suite passed unchanged (2792 passed) before any
    new tests were written. 10 new tests added to `tests/
    test_search_execution.py` (5 per spell: refusal/immunity gating,
    win, loss/escape, and the leader-target speed default) -- 2802
    passed total.

- **Phase 238**: wires Augur Combat [AC], the third and last
  of the originally-identified "formula ready, never dispatched" secret
  Personal-Combat spells (Gate Demon and Lava Pool closed in Phase
  237) -- completing the full Gap 2 spell-wiring effort (Illusory Hero
  was already separately confirmed complete in Phase 211). Its own
  primitives (`AUGUR_COMBAT_SHIRK_CHANCE`, `augur_combat_shirk_chance()`,
  `resolve_augur_combat_shirk()`, `resolve_augur_combat()`,
  `AUGUR_COMBAT_FREE_WHEN_CAST_FIRST`,
  `AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER`) were already built in
  `turn/encounter.py`'s own Phase 205 addendum, which had explicitly
  left the "silent battle simulation" itself as "the caller's job."
  - **`is_first_tactic` threading**: `AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_
    CAST_LATER` needs the spell's own true position within the caster's
    *full* plan, not just among its own `CAST` entries -- threaded a new
    `is_first_tactic` parameter through `_resolve_cast_tactic()`,
    `_resolve_cast()`, the main leader tactic loop (now `enumerate()`),
    and `_resolve_monster_casts()` (rewritten to walk `monster_plan`
    directly instead of a pre-filtered `monster_cast_tactics` tuple,
    which could no longer answer "true position").
  - **The "silent battle simulation"**: modeled as one real, throwaway
    `resolve_melee_duel()` call on `dataclasses.replace()`-cloned
    combatants, discarded after reading only the winner -- reusing the
    exact mechanic that would actually decide the encounter, rather
    than inventing a separate win-probability estimator formula
    (`estimate_win_probability` exists elsewhere but is a structurally
    different army-Duel approximation, not applicable to personal
    hit-points combat). The clones never touch the real caster/target.
  - **Cast first** (`is_first_tactic=True`): runs the simulation, then
    `resolve_augur_combat()` rolls the courage-gated shirk chance (only
    if the simulation shows the caster losing) -- a shirk ends the
    encounter as a Flee, matching `AUGUR_COMBAT_FREE_WHEN_CAST_FIRST`
    ("Usually this spell should be the first tactic ordered, when it
    won't cost you a combat round").
  - **Cast later** (`is_first_tactic=False`): "if it comes later, then
    the result will be an attempt to flee" -- reuses the exact real
    `Maneuver.FLEE` roll (`rng.random() < FLEE_CHANCE[stats.speed]`), no
    simulation attempted.
  - **`LeaderState.temper is None`**: no basis to model the
    courage-gated shirk roll, so (the same "insufficient data, no
    effect" convention every spell in this dispatcher already uses for
    an unresolvable precondition) the cast-first branch has no effect.
  - **Monster caster**: a documented no-effect -- confirmed via grep
    that Augur Combat never appears in any real `monster_encounter_
    plan.py` species plan (the same "not reachable" situation Illusory
    Hero's own docstring already documents), and a monster has no
    `Temper` to shirk with regardless.
  - `turn/encounter.py`'s own "not wired into `turn/search_execution.py`"
    confession corrected to reflect the new wiring.
  - Non-breaking: full suite passed unchanged (2802 passed) before any
    new tests were written. 8 new tests added to `tests/
    test_search_execution.py` (monster-caster no-effect, cast-later
    flee success/failure, cast-first no-Temper no-effect, simulated
    win never shirks, simulated loss shirks-and-flees, simulated loss
    without shirk falls through, and an unmocked integration test
    confirming the simulation doesn't mutate the real combatants) --
    2810 passed total.

- **Phase 239**: Steal [ST] success formula (`turn/
  encounter.py`), wired into `turn/search_execution.py`'s tactic walk
  -- closing the codebase-wide gap audit's own concrete finding
  ("Formula di successo Steal inesistente" / "8 tattiche di Search non
  agganciate", of which Steal is the one with a real, sourced
  formula). Quoted in full by the user (project author), rulebook
  [5.4]: "La probabilita' base di riuscita e' del 15% piu' 15% per
  livello di abilita' ... se il ladro prende di mira un personaggio che
  e' alla guida di un esercito le sue probabilita' di riuscita sono
  dimezzate ... le probabilita' di evitare la cattura sono in funzione
  del livello di abilita' del ladro ... se si tenta di derubare un
  mostro, questi tentera' di nascondere il suo tesoro ... 10% ... se e'
  piu' furbo la probabilita' puo' salire fino al 25% o al 50%."
  - `steal_success_chance()`: 15% base + 15%/level, halved against an
    army-commanding target, capped at 95% (the Thief Mastery I-V
    ability's own tooltip text: "the maximum chance is always 95%",
    read as the cap on the overall formula, not just that ability's own
    bonus).
  - `steal_evasion_chance()`: the rulebook gives no numeric formula for
    evading capture after a failed attempt ("in funzione del livello"
    only) -- confirmed with the user directly as project-original,
    structured like the sourced success formula (base + per-level) but
    with distinct, unsourced numbers (30% base, +10%/level, capped at
    90% -- deliberately different from the sourced 95% cap).
  - `resolve_monster_hides_treasure()`/`STEAL_MONSTER_HIDE_TREASURE_
    CHANCE`/`StealTargetCunning`: the monster's own countermeasure
    roll, three buckets (10%/25%/50%, quoted verbatim above).
    `MONSTER_STEAL_CUNNING` maps every real species to a bucket by
    collapsing the existing, real per-species `MIRROR_IMAGE_MONSTER_
    INTELLIGENCE_TIER` (Phase 187, six tiers) down to three -- an
    interpretive collapsing (the Steal text gives no per-species
    breakdown of its own), not a guess at the 10/25/50% figures
    themselves.
  - **Search wiring** (`_resolve_steal()`): Search's target is always
    the guardian monster, never a King/Hero, so only one of the
    rulebook's three caught-thief consequences applies -- "si ha un
    combattimento individuale, a una distanza scelta a caso" (personal
    combat at a random range). Spell range has no resolvable outcome
    (no spell-effect system exists anywhere in this project) and is a
    documented no-effect, not a silent substitution for one of the
    other two ranges; Bow/Melee range reuse the exact real
    `resolve_fire_arrow_duel()`/`resolve_melee_duel()` mechanics. No
    `target_leads_army` halving either, since a guardian monster never
    commands an army in this project's model. A successful theft loots
    the feature exactly like a combat win (`_outcome_from()`, the same
    machinery every other terminal Search outcome already uses).
  - **Confirmed out of scope for this phase, not attempted**: the
    King-gold-theft magnitude ("dipende da quanto ha nella tesoreria",
    no formula given) and the King/Hero-target capture consequences
    (execution, ransom) -- neither is reachable from Search, whose
    target is always a monster; a future Challenge/Pursue-side Steal
    wiring would still need them. `Talk`/`Say`/`Give`/`Fulfill`/
    `Scout`/`Use_MI`/`Beg` remain unwired -- no rulebook text for their
    own mechanics has been supplied yet.
  - Two stale "not yet wired" docstring paragraphs corrected during the
    same audit that motivated this phase (found to already be fixed,
    Phase 18 and Phase 199 respectively): `turn/hire_fire_decode.py`'s
    nested-plan-parsing paragraph, and `turn/valhalla_execution.py`'s
    own Gate Angel/Valhalla-visit wiring paragraph.
  - Non-breaking: full suite passed unchanged (2810 passed) before any
    new tests were written. 15 new tests added (9 in `tests/
    test_encounter.py` covering the success/evasion formulas, the
    monster-hide table, and the cunning-tier mapping; 6 in `tests/
    test_search_execution.py` covering hidden-treasure fall-through,
    a successful loot, evaded-capture fall-through, and all three
    caught-thief combat ranges) -- 2825 passed total.

- **Phase 240**: Talk [TA] and Say [SA], wired into `turn/
  search_execution.py`'s tactic walk; Fulfill [FU] researched and
  confirmed out of scope. Rulebook [5.5]-[5.7], quoted in full by the
  user (project author), from a file titled "TALK SAY FULFILL.txt"
  (their own paraphrase of the printed rulebook, plus a per-species
  "DR" table).
  - **Talk's DR gate**: `TALK_MONSTER_DRUID_LEVEL_REQUIRED`, sourced
    from `HostAK/TP/CTME.PAS`'s own `talkdiff` table -- "DR" is that
    table's column header, confirmed as the Druid ability's own
    abbreviation (`CTBOTH.PAS` line 151: `'DR','TH','EX','SP','SA'`).
    Cross-checked exhaustively against the user's own supplied table:
    43 of 60 species agreed exactly; the 17 that disagreed (Beholder,
    Black Dragon, Chimera, Elemental Sorceror, Gargoyle, Ghost, Giant,
    Giant Clam, Giant Worm, Green Dragon, Hydra, Imp, Mermaid, Mummy,
    Spectre, Troll, Werewolf) were resolved in the Pascal table's
    favor, confirmed directly by the user.
  - **The Attack/Ignore/Deal reaction**: no numeric split exists
    anywhere in either source -- `Get_Reply`/`Check_RWish` (`DEF2.PAS`,
    inside `{$IFDEF Moderator}`) turned out to be tooling for a *human*
    moderator to manually judge pre-scripted quest content
    (`_qplotno`), not an automated formula. Confirmed directly with the
    user: project-original values (`resolve_talk_reaction()`, 40%
    Attack / 35% Ignore / 25% Deal), with a Druidic-aligned caster's own
    Attack chance nearly halved (20%) and the freed probability added
    to Deal, per the rulebook's own "maggiormente disposto ad
    aiutarlo" ("more inclined to help") text.
  - **Search wiring**: Attack/Ignore both leave the encounter
    unresolved (no special effect, the plan's own next tactic decides
    what happens); Deal ends the Search honestly unresolved
    (`combat_resolved=False`, no winner) rather than as a combat
    win/loss, since Fulfill's own persistence doesn't exist (below). A
    second rulebook case -- talking to an independent wandering Hero
    reveals Alignment/Temperament/hire cost -- is confirmed out of
    scope: Search's own target is always the guardian monster, never a
    character.
  - **Say**: "non fa consumare tempo di combattimento" ("doesn't
    consume combat time") turned out to already be exactly what the
    tactic walk's own "unwired maneuvers are silently skipped" fallback
    does -- given its own explicit `Maneuver.SAY` branch purely to
    document that this is deliberate, not incidental. No new behavior.
  - **Fulfill, confirmed out of scope, not attempted**: "dopo aver
    accettato le sue condizioni" ("after accepting its conditions"),
    together with "Non è possibile usare sia la tattica Talk che
    Fulfill nello stesso Piano d'Incontro" (Talk and Fulfill can't
    share an Encounter Plan), reads as Fulfill honoring a deal a
    *previous turn's* Talk already secured -- needing a "this Feature
    has a pending deal with this leader" state persisted on
    `Feature`/`GameState` across turns that doesn't exist anywhere in
    this project (the same class of gap as the still-unbuilt treasure/
    monster/rumor content-generation system).
  - Two fixed-in-passing regressions in pre-existing Phase 238 tests:
    both used `Maneuver.TALK` as an inert "something else came first"
    placeholder tactic, which broke once Talk stopped being a no-op
    (`Monster.ARCHER`'s own 0-level DR requirement meant the placeholder
    now actually rolled a reaction). Swapped to `Maneuver.GIVE`, still
    genuinely unwired.
  - Non-breaking: full suite passed unchanged (2825 passed, after
    fixing the two regressed Phase 238 tests above) before any new
    tests were written. 11 new tests added (5 in `tests/
    test_encounter.py` covering the DR-table coverage/spot-values, the
    gate check, and the reaction-roll boundaries including the Druidic
    shift; 6 in `tests/test_search_execution.py` covering the DR gate,
    Attack/Ignore/Deal outcomes, the Druidic bonus actually being
    wired, and Say's own no-op) -- 2836 passed total.

- **Phase 241**: Beg [BE], wired into `turn/search_execution.
  py`'s tactic walk. No Pascal source and no rulebook text survive for
  this tactic -- exhaustively confirmed: `CBeg` appears only in
  `CTBOTH.PAS`'s own `maneuver` enum declaration, never referenced by
  name anywhere else in the available archive (no table, no
  `Plan_Intent()` entry, no narrative template). Designed
  collaboratively with the user (project author), who proposed the
  starting concept directly ("Quando un personaggio Codardo chiede
  pietà a un mostro o a un altro eroe per evitare di essere ucciso?")
  and then answered three design questions:
  - **Timing**: only as a last resort after having taken a hit ("Solo
    come ultima risorsa dopo un colpo subito"). Checked via
    `Combatant.hit_points < CHARACTER_HIT_POINTS` -- every combatant
    starts at the flat rulebook [5.0] value (10), so this needs no new
    field, just a comparison against the character's own current
    hit points.
  - **Audience**: only monsters intelligent enough to understand a plea
    can grant mercy ("Solo mostri con intelligenza sufficiente").
    Reuses the existing, real per-species `MIRROR_IMAGE_MONSTER_
    INTELLIGENCE_TIER` (Phase 187) directly rather than inventing a new
    mapping, using all six of its tiers (not collapsed to three buckets
    the way Steal's own cunning table was in Phase 239 -- that collapse
    was appropriate there because the source text only gave three
    numbers to bucket into; here there's no source numbers at all, so
    the finer six-tier table was kept).
  - **Outcome**: a successful plea ends the encounter exactly like a
    successful Flee -- the character escapes unharmed ("Il personaggio
    fugge illeso (come una Flee riuscita)").
  - **Mercy chances, project-original** (`BEG_MERCY_CHANCE`): no source
    gives numbers, only the qualitative "sufficiently intelligent" gate
    above -- `DIVINE_OR_SUPERHUMAN: 60%, HIGH_HUMAN: 45%, MEDIUM_HUMAN:
    30%, LOW_HUMAN: 15%, ANIMAL: 0%, MECHANICAL: 0%`. Animal/Mechanical
    are a flat 0%, not just "unlikely" -- confirmed unable to even
    understand a plea, matching the user's own "solo mostri con
    intelligenza sufficiente" framing.
  - **Search wiring** (`_resolve_beg()`): an undamaged leader gets no
    effect at all, no roll consulted (a documented no-effect, not an
    oversight). Once damaged, the guardian's own species is looked up
    in `MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER` (defaulting to `ANIMAL`
    -- zero mercy -- for any species missing from that table) and
    `resolve_beg_for_mercy()` rolls once; success returns the same
    `SearchExecutionResult(accepted=True, combat_resolved=False,
    fled=True)` shape a successful Flee already uses, failure falls
    through to the plan's own next tactic.
  - Non-breaking: full suite passed unchanged (2836 passed) before any
    new tests were written. 9 new tests added (5 in `tests/
    test_encounter.py` covering the six-tier coverage, the Animal/
    Mechanical zero, the monotonic increase by intelligence, and the
    roll boundary; 4 in `tests/test_search_execution.py` covering the
    undamaged no-effect, an Animal-tier monster's guaranteed refusal,
    and both the success and failure branches for a damaged leader) --
    2845 passed total.

- **Phase 242**: world generation (`turn/world_generation.py`,
  new) and Explore's own feature-discovery roll
  (`turn/exploration.py discover_features()`), closing the two gaps
  `models/feature.py`'s own docstring had flagged since Phase 75 --
  "populating a game's feature roster (world generation)" and the
  when/probability of discovering one during Explore. **No Pascal
  source survives for either**: the real world-generator, `HostAK/TP/
  AKGEN.EXE`, is compiled-only (confirmed by an exhaustive listing of
  the whole archive -- every other `.EXE` there has a matching `.PAS`,
  `AKGEN.EXE` doesn't), and the discovery-trigger logic lived
  exclusively in the missing main turn-processor (`fdisc`/`nfeatures`
  are only ever *read* by `REPORTS.PAS`, never written, anywhere in the
  available source). Everything below is project-original, designed
  collaboratively with the user (project author) via direct
  confirmation, cross-referenced against the one real survivor
  (`MONSTER_GUARDED_FEATURE_TYPES`, Phase 79) wherever possible.
  - **World generation density, confirmed directly by the user**: land
    provinces get a feature 60% of the time, and 20% of *those* get a
    second, independently-generated feature; sea provinces get a
    feature 10% of the time, always aquatic-guarded.
    `Terrain.NO_TERRAIN` provinces never get one.
  - **Terrain-gating, confirmed directly (yes)**: `SEA_FEATURE_TYPES`
    reserves `MAG_POOL`/`MAELSTROM` for sea provinces -- sourced
    directly, every monster `MONSTER_GUARDED_FEATURE_TYPES` ever pairs
    with either type (`GI_OCTOPUS`, `GI_CLAM`, `ELASMOSAURUS`,
    `GW_WHALE`, `MERMAID`) is one of this project's own aquatic
    species -- plus `UND_CAVERN` ("Undersea Cavern"), added by name
    evidence alone. All other 27 real `FeatureType` members are
    land-only.
  - **Guardian selection**: `FEATURE_TYPE_CANDIDATE_MONSTERS` inverts
    `MONSTER_GUARDED_FEATURE_TYPES` (a monster's own primary/secondary
    type both count). Only 16 of 30 real types have any sourced
    candidate; the sea types are always covered (`UND_CAVERN` seeded
    with the same aquatic candidates as `MAG_POOL`/`MAELSTROM`), and
    the 14 uncovered land types fall back to a uniform draw over every
    non-aquatic monster (`LAND_MONSTER_POOL`, 55 species) -- an
    explicit, documented fallback, not a silent gap.
  - **Treasure**: a uniform-random draw over the full 113-member
    `Treasure` catalog (Phase 77) -- no source ties treasure to feature
    type, monster, or any notion of "tier."
  - **Discovery trigger, confirmed directly (use %-exploration as the
    probability)**: `discover_features()` rolls, independently per
    still-undiscovered feature, `exploration_percent` as a 0-100 chance
    -- monotonically increasing and guaranteed once a kingdom's own
    cumulative exploration of the province reaches 100%, directly
    matching [3.2]'s own "must Explore 100%... to make sure everything
    ...has been found." A successful roll sets full disclosure
    (`discovery_level` 3, matching Explore's own "told the name...
    treasure... and the monster guarding" text) rather than a partial
    level. Also closes a previously-flagged gap in passing: `Feature.
    magically_hidden` (Phase 193, Hide Feature) finally has its first
    real consumer -- a hidden feature is skipped, not rerolled.
  - **Wiring**: `record_kingdom_exploration()` (`turn/move_execution.py`,
    the one choke point already shared by the Explore action, Move's
    own partial-exploration side effect, and the multi-attacker LMOVE
    path in `turn/turn_processor.py`) gained optional `state`/`rng`
    parameters -- passing `state` rolls discovery using the newly-
    updated percentage, `state=None` (the default) preserves every
    pre-Phase-242 caller's exact behavior. All three real call sites
    now pass `state`/`rng`.
  - **Search's own win branch now grants the treasure**: `feature.
    treasure` (new `Feature` field, `None` unless world generation set
    one) is granted to the winning leader via the existing item
    registry (`GameState.add_item()`, Phase 140) inside
    `_outcome_from()`'s own `winner == "a"` branch, alongside the
    pre-existing `looted = True` flip.
  - **Confirmed out of scope, not attempted**: the [3.2] rumor
    mechanic ("sometimes you get rumours of previously unheard-of
    features... about half... are true") -- a separate discovery
    channel from direct Explore, whose prose templates
    (`HostAK/TP/PROSE/FRUMOR.X`) exist but whose selection/
    falsification logic doesn't survive either. Deferred to a future
    phase, same "documented gap, not a guess" treatment as everything
    else here.
  - Non-breaking: full suite passed unchanged (2845 passed) before any
    new tests were written. 22 new tests added (11 in `tests/
    test_world_generation.py`, new file, covering the land/sea type
    partition, candidate-monster coverage, the density/double-feature/
    guardian/treasure rolls, and sequential feature-id assignment; 6 in
    `tests/test_exploration.py` covering `discover_features()`'s
    success/failure/already-discovered/magically-hidden/per-kingdom/
    boundary cases; 2 in `tests/test_move_execution.py` and 1 in
    `tests/test_plan_dispatch.py` covering the `record_kingdom_
    exploration()`/dispatch wiring; 2 in `tests/test_search_execution.py`
    covering the treasure grant and its absence) -- 2867 passed total.

- **Phase 243**: rumors (rulebook [3.2] -- "Sometimes you get
  rumours of previously unheard-of features in your turn reports.
  About half of these rumours are true, but the rest are false in some
  respect..."), the one piece of [3.2] Phase 242 explicitly deferred.
  `models/rumor.py` (new, the `Rumor` record + `RumorContent` enum) and
  `turn/rumor.py` (new, the trigger/selection/falsification logic).
  Same "prose templates survive (`HostAK/TP/PROSE/FRUMOR.X`), the logic
  doesn't" finding as world generation itself -- everything below is
  project-original, confirmed directly with the user (project author).
  - **Trigger chance, by order type, confirmed directly**: Move/
    Pursue/Trail 20%, Explore/ASpy 30%, Cast/Practice 5%. Resolved from
    the user's own shorthand (MO/PU/TR, EX/SP, CA/PR) against this
    project's own Pascal-sourced `actab` abbreviation table
    (`CTBOTH.PAS`, positionally matched against the `action` enum --
    unambiguous: MO=LMove, PU=Pursue, TR=Trail, EX=Explore, SP=ASpy,
    CA=Cast, PR=Practice).
  - **Eligibility, confirmed via `find_rumor_candidates()`**: only
    features not yet discovered by the hearer's own kingdom ("previously
    unheard-of"), not magically hidden (Phase 193's own first real
    consumer), and within 2 hexes of the order's own province --
    excluding that province itself (a feature right where the character
    already is would just be found directly by Explore's own
    `discover_features()`, Phase 242, not "heard about"). Checked
    *before* rolling the trigger chance at all, so this is a true no-op
    -- zero randomness touched -- for any `GameState` with no nearby
    features, i.e. every pre-Phase-243 caller and test.
  - **Content, confirmed directly**: 70% names the feature's own
    guardian monster, 30% its own treasure item -- both always naming a
    province too. A feature missing one of the two is only eligible for
    whichever content type it actually has (a feature with neither
    isn't a candidate at all).
  - **Truth, confirmed directly**: 50/50, matching "about half... are
    true." A false rumor corrupts exactly one detail (50/50 between the
    two), matching "the treasure may not actually be there, and/or the
    feature may be in a different province": either the monster/item
    (replaced with a uniformly-random *different* one) or the province
    (replaced with a uniformly-random *other* province on the map -- no
    stated range for how wrong a false province can be).
  - **Wiring**: a single choke point, `dispatch_phase()`
    (`turn/plan_dispatch.py`), rolled once per dispatched phase whose
    own `ActionCode` is rumor-eligible, using the leader's own
    pre-order location. A new append-only `GameState.rumors` registry
    (`add_rumor()`/`new_rumor_id()`/`rumors_heard_by()`) mirrors the
    battle-death graveyard's own "no turn-events log yet" pattern --
    nothing renders a rumor into report prose yet, the same "record
    exists, no consumer yet" gap several earlier phases already
    documented for their own new state.
  - Non-breaking: full suite passed unchanged (2867 passed) before any
    new tests were written -- the "no candidates, no randomness
    touched" design meant zero pre-existing tests needed fixing, unlike
    several earlier phases' own wiring work. 21 new tests added (16 in
    `tests/test_rumor.py`, new file, covering the trigger-chance table,
    every `find_rumor_candidates()` exclusion rule, and
    `resolve_rumor_generation()`'s trigger boundary, true/false split,
    content split, subject-vs-province corruption, and the guardian-
    only/treasure-only fallback; 3 in `tests/test_game_state.py`
    covering the new registry; 2 in `tests/test_plan_dispatch.py`
    covering the dispatch wiring, including the no-features no-op) --
    2888 passed total.

- **Phase 244**: renders a `Rumor` (Phase 243) into turn-report
  prose -- the one gap Phase 243 explicitly left open ("nothing renders
  a rumor into report prose yet"). `report/turn_report.py
  describe_rumor()` (new), plus `_FRUMOR_MONSTER_TEMPLATES`/
  `_FRUMOR_ITEM_TEMPLATES` (new, adapted from `HostAK/TP/PROSE/FRUMOR.X`,
  quoted in full below).
  - **A genuine conflict between the real Pascal template and Phase
    243's own confirmed design, resolved directly with the user**:
    `FRUMOR.X`'s real sentence always names *both* the guardian monster
    and the treasure in one clause ("`& inhabited/Roccupied by +, who
    guards/holds the \`"), but Phase 243's own confirmed design reveals
    only *one* detail type per rumor (70% monster, 30% item -- the
    other is never known). Asked the user directly rather than guessing
    which side to bend; the user chose "adapt the sentence, omit the
    missing detail" -- every clause that doesn't touch the omitted
    detail stays verbatim (including the source's own double-space
    idiosyncrasies), only the tail clause naming the omitted detail is
    dropped/replaced. This produces **two** adapted 4-variant template
    sets, not FRUMOR.X's own single 4-variant set reused unmodified.
  - **`$#` marker, resolved from `report/prose.py`'s own marker table**:
    the real template uses `$#` (not `@`, the resolved-province-name
    marker) for the province, since the hearer hasn't actually visited
    it -- `$` is a literal character (Pascal's own hex-literal notation
    idiom, already visible unescaped elsewhere in the archive), `#` is
    `report/prose.py`'s own "a number" marker. Rendered via
    `turn/hex_numbering.py encode_hex_number()`, the exact inverse of
    the `decode_hex_number()` every LMove order already uses -- not
    previously imported into `turn_report.py`, added this phase.
  - **`describe_rumor(rumor, state, character_name, board_width, rng)`
    takes `state` directly**, matching `describe_bystander_spell_
    notice()`'s own precedent, rather than only plain caller-supplied
    strings like `describe_give()`/`describe_hire()`: the feature's own
    *kind* is never falsified by Phase 243's own design (only the
    guardian/treasure/province can be), so it's looked up straight from
    `state.features[rumor.feature_id]`. Dispatches on `rumor.content`
    to pick the monster-set or item-set templates; renders whatever
    `rumor` says regardless of `rumor.is_true` -- a false rumor is
    supposed to read exactly like a true one to the kingdom that heard
    it, that's the entire point of it being false.
  - Non-breaking: full suite passed unchanged (2888 passed) before any
    new tests were written. 4 new tests added to `tests/test_turn_
    report.py` covering the monster-content variant, the item-content
    variant, that the rendered location comes from `rumor.
    described_coord` (not the feature's real coordinate -- the false-
    rumor-corrupts-the-province case), and that `pick_variant()`'s
    selected index actually drives which of the 4 variants renders --
    2892 passed total.

- **Phase 245**: renders the in-person discovery half of [3.2]
  -- `discover_features()`'s own results (Phase 242), rolled every
  EXPLORE dispatch but thrown away ever since, are now surfaced and
  narrated. `report/turn_report.py describe_feature_discovery()` (new),
  from `HostAK/TP/PROSE/FINDFEAT.X` -- FRUMOR.X's own sibling template,
  quoted in full above the new code. Unlike FRUMOR.X, the real sentence
  never mentions a treasure at all, only the feature and its guardian
  monster, so this is a straight 4-variant transcription -- no
  FRUMOR.X-style adapt-and-split conflict to resolve here.
  - **The actual gap closed, confirmed by direct code inspection, not
    guessed**: `turn/move_execution.py record_kingdom_exploration()`
    has called `discover_features()` and returned only the new
    percentage since Phase 242 -- the `list[Feature]` it discovered was
    computed and discarded every single call. None of its 3 real
    callers (`execute_move()`, `turn/plan_dispatch.py`'s own EXPLORE
    branch, `turn/turn_processor.py`) ever captured the return value at
    all, confirmed by grep before touching the signature.
  - **`record_kingdom_exploration()` now returns
    `KingdomExplorationResult(new_percent, discovered_features)`**
    instead of a bare `int` -- a small, typed, additive change (2
    pre-existing test assertions updated from `x == int` to
    `x.new_percent == int`, both already the only 2 places anywhere
    that captured the old return value). `ExploreResult` (the pure,
    state-free result of `resolve_explore()`) itself stays unchanged in
    shape but gains a `discovered_features: list[Feature] = field(
    default_factory=list)` field with a safe empty default -- filled in
    by `dispatch_phase()`'s own EXPLORE branch after calling
    `record_kingdom_exploration()`, not by `resolve_explore()` itself
    (a pure percent-only function with no `GameState`/`rng` to roll
    discovery with).
  - `describe_feature_discovery(feature, character_name, province_name,
    rng)` assumes `feature.guardian_monster` is set, matching every
    feature `turn/world_generation.py` actually creates (Phase 242
    confirmed every generated feature always gets a guardian) -- not
    defensively guarded, same "trust the caller" stance already taken
    elsewhere in this module (e.g. `describe_rumor()` doesn't guard a
    `None` `described_monster` either).
  - Non-breaking: full suite passed unchanged (2892 passed, after fixing
    the 2 pre-existing assertions above) before any new tests were
    written. 4 new tests added: 2 in `tests/test_turn_report.py`
    (first-variant exact string, variant-selection), 1 assertion added
    to the existing Phase 242 dispatch test in `tests/
    test_plan_dispatch.py` (`result.discovered_features == [feature]`),
    1 assertion added to an existing `tests/test_move_execution.py`
    test (`exploration.discovered_features == [feature]`) -- 2894
    passed total.

- **Phase 246**: wires `models/monster.py
  roll_monster_alignment()` (Phase 176) into world generation --
  a pure, fully-tested mechanism that had nothing to wire it to
  when it was built ("this project still has none [of a world-
  generation pipeline]", that phase's own note), unblocked now
  that `turn/world_generation.py` (Phase 242) *is* that pipeline.
  `turn/world_generation.py _create_feature()` now rolls the
  guardian's own Alignment right after picking it, stored in a new
  `models/feature.py Feature.guardian_alignment: Alignment | None`
  field (`None` for a feature with no guardian, or one built outside
  world generation -- most existing tests -- same convention
  `treasure` already established).
  - **Also corrected two stale "deliberately not wired anywhere"
    docstring claims found while touching this area**: `models/
    monster.py`'s own `roll_monster_alignment()` docstring (Phase
    176) and `MONSTER_MAGIC_ABILITIES` docstring (Phase 177) both
    still said so, even though Phase 209 already wired
    `MONSTER_MAGIC_ABILITIES` into `turn/search_execution.py`'s CAST
    orchestration engine. Both struck through and corrected in place
    rather than left to mislead a future reader, the same "fix stale
    docs found in passing" practice used for Phase 244's own README
    correction.
  - Non-breaking check surfaced one real rng-consumption change (not a
    bug, an expected side effect of adding a new roll):
    `test_generate_world_features_sea_success_uses_aquatic_guardian`'s
    scripted guardian (`Monster.GI_OCTOPUS`) has a 2-option alignment
    distribution, so it now consumes one extra `rng.random()` call the
    test's script didn't provide -- fixed by adding the missing
    scripted value, not by changing behavior. Every other existing
    `test_world_generation.py` test happened to pick a single-option
    guardian (`Monster.R_DRAGON`, 100% Evil), so they were unaffected --
    confirmed by checking each one's actual guardian pick rather than
    assumed. 2 new tests added (1 confirming the single-option
    zero-roll case, 1 driving both sides of a two-option 50/50 split to
    prove the roll's outcome actually reaches `Feature.
    guardian_alignment`, not just that a call happens) -- 2895 passed
    total.

- **Phase 247**: wires `EXPLORE` discovery and rumor
  narration into `describe_turn_results()` -- the real top-level
  per-turn assembler (Phase 142+), already calling `describe_*`
  composers for HIRE/FIRE/PRACTICE/CAST/USE_MI/TRADE/PURSUE/TRAIL/
  SEARCH/ASPY, but never reaching `describe_feature_discovery()`
  (Phase 245) or `describe_rumor()` (Phase 244) despite both already
  existing and being fully tested.
  - **`EXPLORE`**: a new branch renders `describe_feature_discovery()`
    for every `ExploreResult.discovered_features` entry -- the
    province is always the discoverer's own current one, so
    `feature.coord` resolves it directly via `_province_label()`.
  - **Rumors needed a real, confirmed gap closed first**: `Rumor`
    (Phase 243) recorded `kingdom_id` but not *which* leader heard it,
    so `describe_rumor()`'s own `character_name` argument (Phase 244)
    had nobody to name. New `Rumor.leader_id` field, threaded through
    `turn/rumor.py resolve_rumor_generation()`/`_build_rumor()` from
    `turn/plan_dispatch.py`'s own rumor-roll block, which already had
    the ordering leader in scope the whole time.
  - **Rumors don't attach to any one `PhaseDispatchResult` entry** --
    `resolve_rumor_generation()` is a side effect of `dispatch_phase()`
    itself, decoupled from whatever action-specific result it returns.
    Rendered as a separate pass after the main walk: for every distinct
    `leader_id` present in `results`, every `Rumor` in `state.
    rumors_heard_by(leader.kingdom_id)` whose own `leader_id` matches
    gets narrated.
  - **Opt-in via a new `board_width: int | None = None` keyword-only
    parameter** on `describe_turn_results()` -- `describe_rumor()`
    needs it to encode the described province's raw hex number, and
    every pre-Phase-247 caller (this whole module's own extensive test
    suite included) has no board width to supply, so omitting it skips
    rumor narration entirely rather than forcing a new required
    parameter onto every existing caller. Not threaded further up into
    `describe_letter_reports()`/`compose_letter_report()` yet -- a
    narrower follow-up gap, not attempted here, to keep this phase's
    own blast radius to the one function actually in scope.
  - Non-breaking: full suite passed unchanged (2895 passed) before any
    new tests were written -- both the `EXPLORE` branch and the
    opt-in `board_width` default mean zero existing test scripts needed
    touching. 4 new tests added to `tests/test_describe_turn_results.py`
    (`EXPLORE` discovery narration; rumors omitted without
    `board_width`; rumors rendered when supplied; a rumor heard by one
    leader in a kingdom isn't narrated for a different leader's own
    results) -- 2899 passed total.

- **Phase 248**: propagates `board_width` the rest of the way
  up the call chain -- from `describe_turn_results()` (Phase 247) into
  its two real callers, `describe_letter_reports()` (Phase 217) and
  `compose_letter_report()` (Phase 215) -- so a full end-to-end King's
  letter report can actually narrate the rumors its own King and
  fellow leaders heard this turn, not just a bare `describe_turn_
  results()` call in isolation. This closes the exact follow-up gap
  Phase 247's own docstring flagged as out of scope for itself.
  - Both functions gain the same `board_width: int | None = None`
    keyword-only parameter, forwarded as-is to their own internal
    `describe_turn_results()` call(s) -- `compose_letter_report()`
    forwards it to both of its calls (ACTION REPORT and, via
    `describe_letter_reports()`, LETTER REPORTS).
  - Same opt-in convention as Phase 247 (and, before that, Phase
    242's `state=None`/`rng=None` and Phase 245's `discovered_
    features` default): `None` by default, so every pre-Phase-248
    caller -- including this module's own large existing test suite --
    keeps its exact prior output with zero rumor narration.
  - Non-breaking: full suite passed unchanged (2899 passed) before any
    new tests were written. 3 new tests added to `tests/
    test_turn_report.py`: `describe_letter_reports()` omits a heard
    rumor without `board_width` and renders it when supplied; a
    `compose_letter_report()`-level test confirms `board_width`
    reaches both ACTION REPORT (the King's own heard rumor) and
    LETTER REPORTS (a different leader's own heard rumor) in one call
    -- 2902 passed total.

- **Phase 249**: wires Illusory Fog's strength-halving effect
  (`AdvancedAbility.ILLUSORY_FOG_SPELL`, Phase 207 addendum) into the
  real battle-strength pipeline -- `turn/cast_execution.py illusory_
  fog_strength()`/`is_illusory_fog_affected_air_unit()` had a fully
  tested primitive since Phase 207, but neither `turn/strength.py` nor
  `turn/battle_orchestrator.py` ever called it, so `ProvinceState.
  illusory_fog_active` had no real effect.
  - `turn/strength.py compute_effective_strength()` gains a new
    `illusory_fog_affected: bool = False` keyword-only parameter,
    applying `illusory_fog_strength()` in the multiplier chain
    alongside `phantasmal_armies_multiplier`/nemesis -- `False` by
    default, so every pre-Phase-249 caller is unaffected.
  - `turn/battle_orchestrator.py _build_battle_units()` looks up
    `state.provinces.get(province_coord).illusory_fog_active` once per
    side, then combines it per-army with a new `_mystic_winds_active_
    for()` helper -- the same "derive from the commanding leader,
    `False` for an unled army" pattern `_phantasmal_armies_level_for()`
    already established -- closing the "no per-army way to derive that
    [Mystic Winds] flag" gap the Phase 207 addendum had originally
    flagged, since `LeaderState.mystic_winds_active` (Phase 204) was
    already sitting right there on the commanding leader.
  - Non-breaking: full suite passed unchanged (2902 passed) before any
    new tests were written. 6 new tests added: 2 in `tests/
    test_strength.py` (halving applied/not-applied at the
    `compute_effective_strength()` level) and 4 in `tests/
    test_battle_orchestrator.py` (a static air unit halved in a fogged
    province; a ground unit unaffected in the same fogged province; a
    Mystic-Winds-led ground unit halved like an air unit; no effect at
    all in an unfogged province) -- 2908 passed total.

- **Phase 250**: wires Mystic Winds' own "the spell ends just
  before the leader gets involved in any military battle between
  armies" clause (Phase 204 addendum), the fact Phase 249's own wiring
  cross-referenced but didn't itself clear. Turned out narrower than
  the Phase 204 addendum originally estimated: grepping every real call
  site confirmed every army-vs-army battle in this project (`turn/
  move_execution.py`, `turn/pursue_execution.py`, `turn/turn_
  processor.py`'s forced-rebattle path, and `fight_multi_attacker_
  battle()`, which itself calls `fight_battle()` once per group) funnels
  through the single real `turn/battle_orchestrator.py fight_battle()`
  function -- so one clearing point covers every entry point the
  addendum named, not four separate ones.
  - New `_clear_mystic_winds_before_battle(armies, state)` helper,
    called for both sides at the very top of `fight_battle()` --
    *before* `_build_battle_units()` runs, so a leader whose
    `mystic_winds_active` was true a moment ago no longer gets Illusory
    Fog's Mystic-Winds-affected treatment (Phase 249) for the very
    battle that ends the spell either -- the literal reading of "ends
    just before," not a guess.
  - Deliberately leaves `ArmyState.movement_points` untouched: "re-
    deriving each affected army's movement" (the addendum's own words)
    has nothing to re-derive *to* -- this project has no per-`ArmyType`
    base movement table anywhere, so a freshly recruited army's own
    `movement_points` defaults to 0, not some army-type-specific normal
    value. Resetting it here to any concrete number would be a guess.
  - Non-breaking: full suite passed unchanged (2908 passed) before any
    new tests were written. 3 new tests added to `tests/
    test_battle_orchestrator.py`: the flag clears for a real attacking
    commander, clears for a real defending commander, and stays
    untouched for an uninvolved leader elsewhere in the same kingdom --
    2911 passed total.

- **Phase 251**: wires `MeritTally.resurrection_bless_casts`
  (Phase 227) -- the Imperial Office Merit Point system's first real
  writer. `turn/merit_points.py`'s own "Gran Sacerdote / Priest"
  section already computed `+1` per successful Resurrection/Bless cast,
  but `turn/cast_execution.py`'s `_execute_resurrection`/`_execute_bless`
  never incremented the tally -- confirmed via grep that no field of
  `MeritTally` had any writer anywhere in the codebase before this
  phase.
  - Both functions now increment `caster.merit_tally.resurrection_
    bless_casts` by 1 immediately before their own `applied=True`
    return -- after `_roll_cast_success()` has already gated the call,
    so a failed cast never counts. The rulebook doesn't distinguish
    which of the two spells scores the point, so both feed the same
    counter; Bless's own independent graveyard-cleanup roll has no
    bearing on whether the cast itself counts.
  - Every other `MeritTally` field (battle counts, monster HP,
    discovery attribution) remains unwired -- this phase closes only
    the one field with a ready consumer and no missing upstream data
    model, not the whole dataclass.
  - Non-breaking: full suite passed unchanged (2911 passed) before any
    new tests were written. 2 new tests added to `tests/
    test_cast_execution.py`: a successful Resurrection increments the
    tally, a successful Bless increments the tally (plus a companion
    assertion on an existing failure-path test confirming a failed
    Resurrection leaves it at 0) -- 2913 passed total.

- **Phase 252**: wires [3.17] Trail's sixth and last named
  field, Actions -- the target's own `ActionCode` for the same phase
  the Trail catches them. `turn/trail_execution.py TrailExecutionResult`
  previously had 5 of 6 named intelligence fields; `actions` was simply
  absent, not merely unpopulated, because `execute_trail()`/
  `advance_trail()` have no visibility into any other leader's own
  same-phase order.
  - Rather than thread that visibility all the way down through
    `plan_dispatch.py dispatch_phase()`/`run_leader_plan()` (both
    heavily-used, central functions many other callers depend on),
    this is wired as a narrower post-dispatch backfill entirely inside
    `turn/turn_processor.py run_turn()` -- the one place that already
    assembles every leader's own `PlanPhase` for the current phase
    label before dispatching any of them. A `leader_id -> ActionCode`
    map is built once per phase from that list, then a new
    `_backfill_trail_actions()` helper stamps the target's own entry
    onto a freshly-dispatched `TrailExecutionResult.actions`
    immediately after dispatch, and the same map is threaded into
    `_continue_active_pursuits()` for `advance_trail()`'s own
    persistent-chase continuation. `execute_trail()`/`advance_trail()`
    themselves are untouched -- `actions`, like `request` before it
    (Phase 213), is caller-populated, not derivable from the state and
    arguments either function is given today.
  - `None` whenever the target had no order this phase at all -- idle,
    or itself mid-chase and excluded from this phase's own entries --
    the same "no data" convention every other Trail field already
    uses, not a guess.
  - Non-breaking: full suite passed unchanged (2913 passed) before any
    new tests were written. 3 new tests added to `tests/
    test_turn_processor.py`: a fresh Trail catch backfills the target's
    own same-phase action; the field is `None` when the target had no
    order that phase; a persistent Trail continuation (via
    `advance_trail()`) backfills it too -- 2916 passed total.

- **Phase 253**: wires [3.14] ASpy's own "taxation of the
  province" line item -- `SAY.PAS`'s `_LSTax` ("Approximate Taxation:
  N"), templated back in Phase 115 (`render_spy_tax_estimate()`) but
  never called from anywhere, and `turn/aspy_execution.py`'s own
  module docstring long claimed outright required "a per-province
  tax-base model this project doesn't have at all."
  - That claim went stale at Phase 222-224: `turn/tax_base.py
    province_tax_yield()` already computes exactly this figure (real
    base `ProvinceState.tax`, minus Scar Terrain's permanent
    reduction, times Bless/Earthquake's own turn modifier) -- the same
    function `describe_finances_report()`'s own "Expected Revenues"
    line already consumes at the kingdom level. Wiring this phase
    needed no new formula, only a new consumer: `SpyReport.
    tax_estimate: int | None` (new field, `execute_aspy()` populates
    it via `province_tax_yield(province)`), and `describe_aspy()` now
    renders `render_spy_tax_estimate()`'s line whenever it isn't
    `None`.
  - Placement confirmed against real Desktop sample files
    (`SE3__T10.K3`/`SE3__T11.K7`): "Approximate Taxation: N" always
    follows the province's own ownership/adjacency narration and
    always precedes "The following elements are present..."/"There
    were no conspicuous characters or forces...". `describe_aspy()`
    renders it right after the recruitable-Army-Type lines and before
    the characters/forces block, consistent with every confirmed
    sample. `None` (base `tax` never recorded) omits the line
    entirely -- the same "omit rather than guess" convention every
    other optional ASpy line item already follows.
  - Non-breaking: full suite passed unchanged (2916 passed) before any
    new tests were written. 4 new tests added: 2 in `tests/
    test_aspy_execution.py` (`tax_estimate` populated from a recorded
    `ProvinceState.tax`; `None` when never recorded), 2 in `tests/
    test_turn_report.py` (`describe_aspy()` renders the line between
    Army Types and the characters/forces block; the line is omitted
    entirely when `tax_estimate is None`) -- 2920 passed total.

- **Phase 254**: wires rulebook page 51's Marshal/Admiral
  Merit Point formula ("TABELLA DELLE CARICHE IMPERIALI",
  `turn/merit_points.py`, Phase 227) into real battle outcomes --
  `MeritTally.land_battles_won_enemy_units`/`lost_own_units` and
  `naval_battles_won_enemy_units`/`lost_own_units` had every consumer
  (the formula functions) and renderer (the Imperial Office report)
  already in place, but nothing anywhere ever incremented them.
  - `turn/battle_orchestrator.py _record_battle_merit()` (new) runs
    once per `fight_battle()` call, right after `battle_result` and the
    Duel's own commander selection are known: the winning side's own
    Supreme Commander is credited `+1 per enemy unit` (the size of the
    *opposing* army fielded, one `ArmyState` = one "unità", not just
    casualties), the losing side's own commander is debited `-1 per own
    unit`, keyed to land vs. naval counters via `terrain is Terrain.SEA`
    (the same land/naval split `_combat_ability_for_terrain()` already
    uses for Tactical vs. Naval ability). An unled side (`None`
    commander -- e.g. the defender's own garrison-commander fallback,
    rulebook [7.1]: "has no abilities") has no leader to credit/debit
    for that side, since it isn't a "battaglia comandata" for anyone; a
    `"tie"` result records nothing for either side, since the rulebook's
    "vinta"/"persa" wording doesn't address one -- both documented
    no-ops, not guesses.
  - Deliberately scoped to just Marshal/Admiral: `MeritTally`'s three
    discovery-attribution fields (Chancellor) and two monster-HP fields
    (Defender) still have no writer anywhere -- the former needs a
    "who found this first" attribution model this project has never
    had, the latter needs its own separate wiring into
    `turn/search_execution.py`'s monster-encounter resolution, a
    meaningfully different call site left for a future phase, the same
    "one field at a time" precedent Phase 251 already set for this same
    dataclass.
  - Non-breaking: full suite passed unchanged (2920 passed) before any
    new tests were written. 6 new tests added to
    `tests/test_battle_orchestrator.py`: `_record_battle_merit()`
    exercised directly for a land win/loss, a naval win/loss, a tie
    (no-op), an unled winning side, and an unled losing side; plus one
    end-to-end `fight_battle()` test confirming a led attacker's real
    Merit Point credit after a genuine conquest -- 2926 passed total.

- **Phase 255**: wires the other half of Phase 254's own
  Defender Merit Point gap -- `MeritTally.monster_hp_defeated`
  (rulebook page 51's "Per ciascun mostro ucciso: totale Punti Ferita
  del mostro") had a real formula consumer (`defender_merit_points()`,
  Phase 227) but no writer anywhere in this project.
  - `turn/search_execution.py execute_search()`'s own `_outcome_from()`
    -- the single point every real "leader wins" branch in that module
    funnels through, whether from Melee, Fire Arrow, or one of
    `_resolve_cast_tactic()`'s own instant-kill spell branches -- now
    credits the guardian's own *starting* hit points (captured once,
    right after the combat stats roll, before anything mutates them)
    to `MeritTally.monster_hp_defeated`.
  - Deliberately only the "killed" half: the rulebook's "metà dei
    punti se neutralizzato con trattative" (half credit for a monster
    negotiated into standing down) needs the Fulfill/Talk-Say
    mechanic `turn/search_execution.py`'s own docstring already flags
    as unwired ("Say, Give, Fulfill, ... silently skipped"), so
    `MeritTally.monster_hp_neutralized` stays at its Phase 59-style
    "field exists, no consumer yet" default -- not guessed at here.
  - Non-breaking: full suite passed unchanged (2926 passed) before any
    new tests were written. 2 new tests added to `tests/
    test_search_execution.py`: a winning Melee encounter credits the
    guardian's own (independently re-derived) starting hit points and
    leaves `monster_hp_neutralized` untouched; a losing encounter
    credits nothing -- 2928 passed total.

- **Phase 256**: wires the Chancellor Merit Point formula's
  Feature half -- `MeritTally.features_discovered_first` ("+2 per
  Special Place discovered first", `turn/merit_points.py`) had the
  skill-level term live since Phase 227 but all three
  discovery-attribution counters unwired.
  - `models/feature.py Feature.discovered_by_kingdom` (a per-kingdom
    dict, Phase 75) already exists and is written by `turn/
    exploration.py discover_features()` every time a kingdom first
    discovers a Special Place -- no new acquisition mechanic was
    needed, only a new consumer. `turn/plan_dispatch.py`'s own
    `ActionCode.EXPLORE` branch now checks, for each feature the
    dispatch just discovered, whether that kingdom's own fresh entry
    is still the *only* one in the dict (nobody beat them to it) and
    credits the acting leader's own tally when so.
  - `discoveries_found_first`/`discoveries_via_espionage` (the
    Invention half) stay unwired -- unlike Features, this project has
    **no acquisition mechanic for a `Discovery` at all**: nothing
    anywhere ever grants a `KingdomState` a `Discovery` in the first
    place (confirmed by an exhaustive search), so there is no event
    yet to attribute "found first"/"via espionage" to. A materially
    larger, still-unscoped gap than this phase's own Feature-side fix.
  - Also fixes a stale docstring sentence found in passing:
    `describe_turn_results()` still claimed rumor narration was "not
    threaded further up into `describe_letter_reports()`/
    `compose_letter_report()` yet" -- Phase 248 actually closed that
    gap already (both composers already forward their own
    `board_width` into every `describe_turn_results()` call they
    make, confirmed by `tests/test_turn_report.py`'s own Phase 248
    tests); only the docstring's own wording was out of date, no code
    change needed.
  - Non-breaking: full suite passed unchanged (2928 passed) before any
    new tests were written. 2 new tests added to `tests/
    test_plan_dispatch.py`: EXPLORE credits the acting leader when
    first to discover a feature; EXPLORE does not credit when a rival
    kingdom's own entry already sits in `discovered_by_kingdom` --
    2930 passed total.

- **Phase 257**: adds a per-line season prefix to the
  GENERAL INTELLIGENCE REPORT's world events, and wires Movement in as
  a fourth real event source -- both sourced directly from `SAY.PAS`.
  - `SEASON_NAME` (`report/turn_report.py`) transcribes `CTBOTH.PAS`'s
    own `seastype`/`seasname` table (`Spring,ESummer,LSummer,Fall,
    EWinter` -> `'spring','early summer','late summer','fall','early
    winter'`, the live `{$IFNDEF Noble}` branch, confirmed against real
    fixture text: 183 "In early winter," occurrences, zero bare
    "winter"), doubly confirmed via `YAK.PAS`'s own real call site
    (`Concat('In ', seasname[seastype(Max(0,Min(4,_rphase)))], ', ')`)
    -- a direct ordinal index into the same 0-4 range this project's
    own `turn_processor.py PHASE_LABELS = ("P0",...,"P4")` already
    tracks. `_season_phrase_for_phase_label()` turns a `PhaseDispatch
    Result.phase_label` into the `"In <season>, "` prefix (or `""` for
    any synthetic, non-"P<N>" label -- `"plague-spread"`,
    `"forced-rebattle"`, ...). `record_battle_world_events()`,
    `record_spell_world_events()`, and (implicitly, since its own
    `phase_label` never matches) `record_plague_spread_world_events()`
    all now prefix every line they record. Deliberately simplified vs.
    the real engine: `SAY.PAS`'s own `phasewrit[kng]` flag only prints
    the season prefix once per (kingdom, phase) run of consecutive
    entries -- reproducing that exactly would need re-deriving each
    kingdom's own consecutive-run grouping at render time, which
    `state.world_events` doesn't preserve (three separate, fixed-order
    recorder passes, not one phase-ordered walk); this project instead
    prefixes every line independently, documented as a real, narrower,
    flagged gap.
  - **Movement wired as a fourth event source, correcting a threshold
    assumption from Phases 231-235**: `SAY.PAS`'s `_LFly` (`Say('<
    flew/Rrode_>_flying_armies into/Rover_to @.',S_Army)`) was found
    tagged `S_Army` -- one severity level *below* `S_Comm` on
    `CTBOTH.PAS`'s own ordinal scale (`S_Prev=0...S_Admin=7,
    S_Army=8,S_Comm=9,S_IDipl=10`), the level every earlier world-event
    source was built against. Real fixture cross-check settled it:
    `SE3__T10.K5:459`'s own GENERAL INTELLIGENCE REPORT reads "In late
    summer, Tlazolteotl (#88) flew over to Waterford." -- third person,
    "(#N)", grouped under "Kingdom of X (#N):", unmistakably GIR
    content despite the lower tag. The true cutoff is therefore
    "`S_Army` or higher," not "`S_Comm` only" -- Phases 231-235 weren't
    wrong for what they covered, just untested against anything
    `S_Army`-tagged until now.
  - A full audit of every remaining `S_Army`/`S_Comm`-tagged `Say()`/
    `Sps()` call in `SAY.PAS` found several other real candidates
    (Scar Terrain's `_STZero`/`_STFite`, King succession's `_LSucc`,
    public theft/ransom, Tidal Wave's `_SWave`, and a large per-battle
    narrative cluster dispatching to unread `PROSE/*.X2` files) -- all
    confirmed to have no real execution-layer trigger anywhere in this
    project (no revenue system, no succession mechanic, no Steal
    execution, no Tidal Wave mechanic, no per-army naming for the
    battle cluster) and are deliberately left unwired, each a distinct,
    separately-scoped follow-up.
  - `render_fly_move_world_event()` renders `_LFly` verbatim.
    `record_move_world_events()` walks `results` for any `moved`/
    `new_location`-shaped entry (duck-typed the same way
    `_battle_reports_from_results()` already duck-types battle shapes)
    and fires the event only when *every* army the mover commands at
    the destination is overflight-capable (`models/army_type.py
    is_overflight_unit()`, Phase 31's existing table) -- **an
    unsourced-but-reasonable heuristic, confirmed directly with the
    user**: the real `Imp_Code` dispatch choosing "flew" vs. the
    ordinary, private `_LMarch` narration lives in the missing main
    program, the same "driver lost, callee kept" gap already documented
    for hex adjacency and world generation. A mover with no armies at
    the destination, or a mixed overflight/ground force, falls through
    to the existing private march narration, untouched.
  - `_LWWalk` (Mystic Winds wind-walking, the other `S_Army`-tagged
    movement notice) stays deliberately unwired: its own trigger,
    `LeaderState.mystic_winds_active`, is a single per-leader flag with
    no record of *which* move set it, and by the time this recorder
    runs (once, after the whole turn resolves) the flag may no longer
    reflect the move being recorded -- attributing it to one specific
    `PhaseDispatchResult` would risk misattribution. No real fixture
    example of this wording was found either, giving nothing to
    validate a design against.
  - Non-breaking: full suite passed unchanged (2930 passed) before any
    new tests were written, after 6 pre-existing tests were first
    updated for the new season prefix they now receive (all five
    `record_spell_world_events()` tests plus the recorded-Plague GIR
    test, every one already using `phase_label="P0"` -> "In spring, ").
    7 new tests added to `tests/test_turn_report.py`: `SEASON_NAME`'s
    full 0-4 mapping; a season prefix on a `record_battle_world_
    events()` line; `render_fly_move_world_event()`'s own template
    rendering; `record_move_world_events()` for an all-overflight army
    (event recorded, season-prefixed), a mixed overflight/ground army
    (skipped), a mover with no army at the destination (skipped), and a
    result that didn't move (skipped) -- 2937 passed total.

- **Phase 258**: wires Fulfill [FU] (rulebook [5.7]) into
  `turn/search_execution.py`, the last unwired Search tactic with a real
  execution-layer path -- and closes the Defender Merit Point formula's
  own remaining gap, `MeritTally.monster_hp_neutralized` (Phase 255 had
  only wired the "killed" half).
  - `Feature.pending_deal_leader_id: int | None` (`models/feature.py`) --
    a deal a prior turn's Talk secured, persisted across turns per
    rulebook [5.6]/[5.7]'s own "dopo aver accettato le sue condizioni"
    ("after accepting its conditions") and "Talk and Fulfill can't both
    be used in the same Encounter Plan." `_resolve_talk()`'s own `DEAL`
    branch now sets it instead of just returning an unresolved result;
    `_resolve_fulfill()` (new) consumes and clears it (whether the
    attempt succeeds or fails), no-opping if this leader holds no
    pending deal on the feature.
  - `resolve_fulfill_honored()` (`turn/encounter.py`) -- **project-
    original, confirmed directly with the user (project author)**: the
    rulebook's own text ("il mostro non sempre tiene fede al suo
    impegno, specialmente se è Malvagio e/o se il suo Allineamento è
    molto differente da quello del personaggio") is entirely
    qualitative, with no numeric formula and no definition of what the
    deal's own "conditions" concretely are -- so this models only the
    abstract "was the deal honored" roll the quote actually describes,
    not invented deal content. Reuses `models/alignment.py
    ALIGNMENT_ORDINAL` (already load-bearing for Hire's ">2 ordinal
    positions apart" rule and `Align_Est`) for the alignment-distance
    penalty, plus a flat penalty when the guardian is confirmed Evil
    (`Feature.guardian_alignment`, Phase 246) -- all three constants
    (`FULFILL_BASE_HONOR_CHANCE=0.75`,
    `FULFILL_ALIGNMENT_DISTANCE_PENALTY_PER_STEP=0.05`,
    `FULFILL_EVIL_PENALTY=0.20`) are unsourced, confirmed design
    choices, the same category `TALK_ATTACK_CHANCE`/`TALK_IGNORE_
    CHANCE`/`TALK_DRUIDIC_ATTACK_CHANCE` already document for Talk's own
    reaction roll. A missing alignment on either side skips the
    distance term rather than guessing a substitute.
  - Success ends the Search peacefully -- `combat_resolved=False`,
    `winner="leader"`, no duel ever fought -- and credits half the
    guardian's own starting hit points to `monster_hp_neutralized`
    (the rulebook's own "metà dei punti se neutralizzato con
    trattative"). No treasure is granted and `Feature.looted` stays
    `False`: unlike a combat win, nothing in the available source ties
    Fulfill's own success to looting the feature. Failure leaves the
    Search unresolved -- the plan simply continues to its next tactic,
    no combat forced.
  - Fixed two stale docstring sentences found in passing while touching
    this exact area: `turn/search_execution.py`'s own module docstring
    still listed Steal/Talk/Say/Cast/Beg as "unwired" (all wired real
    tactics since Phases 209-241) and claimed `monster_hp_neutralized`
    "stays... until [Fulfill] is built" (now built) -- both corrected
    to reflect current state, no code change needed for either.
  - Non-breaking: full suite passed unchanged (2937 passed) before any
    new tests were written. 11 new tests: 6 in `tests/test_encounter.py`
    for `resolve_fulfill_honored()`'s own formula (base-chance boundary,
    alignment-distance penalty, Evil penalty, both stacked, and each
    penalty independently skipped when its own alignment side is
    `None`); 5 in `tests/test_search_execution.py` (Talk's `DEAL`
    reaction now records the pending deal; Fulfill with no pending deal,
    or a pending deal belonging to a different leader, falls through;
    Fulfill honored ends the Search peacefully with the correct
    half-HP credit; Fulfill not honored falls through and still clears
    the pending flag) -- 2948 passed total.

- **Phase 259**: King succession -- when a King dies, a
  Royal Heir now takes the throne under the same `leader_id`, instead
  of the Kingdom simply going permanently Kingless (a real,
  confirmed-reachable gap: `GameState.remove_leader()` is called from
  Duel/Search/Challenge/Pursue losses and Kill_Enemy with zero special
  handling for `is_king`). Sourced directly from **RULES.AK** (not just
  SAY.PAS's own `_LSucc`, confirmed too): [2.1] "Kings" (the King-
  creation formula `models/kingdom.py SkillTable` already cited since
  Phase 21) and [4.21.1] "Resurrect character"'s own Royal Heir
  passage, quoted in full in the code.
  - `LeaderState.is_royal_heir: bool` (`models/game_state.py`) marks a
    throne-holding Heir still awaiting either a
    new King's own skill assignment (a separate, later phase, confirmed
    with the user/project author) or a Resurrection undoing the death.
  - `GameState.remove_leader()`: a dying King (`is_king` and
    `kingdom_id is not None`) still gets archived into `dead_leaders`
    as before, but a fresh Royal Heir is installed into `state.leaders`
    under the same `leader_id` -- same `kingdom_id`/`location`/
    `temper`/`alignment`/`race` as the dead King, `name` unchanged too
    (SAY.PAS `_LSucc`: "will use predecessor's name until next turn"),
    `skills` a fully zeroed `SkillTable` ("the Heir must have zero
    Talents assigned"), `is_king=True`, `is_royal_heir=True`. A Hero's
    death (or a kingless King -- not a real reachable state via
    `kingdom_bridge.py`) still just vanishes, unchanged.
  - `turn/cast_execution.py _execute_resurrection()`: a new branch
    fires when `request.target` is a *living* leader still flagged
    `is_royal_heir` -- RULES.AK: "you can cast a Resurrection spell on
    your Royal Heir and get your old King back... you're actually
    casting the spell on the bones carried around by the Heir... If
    another player casts a Resurrection spell on your Royal Heir, you
    still get your old King back." On success, the exact archived King
    (`dead_leaders`, same `leader_id`) is restored verbatim, keeping
    his own original `kingdom_id` -- "resumes his own throne," not the
    caster's, unlike an ordinary Hero revival, regardless of which
    Kingdom's own priest casts it. Co-location and the merit-tally
    credit both still apply exactly as before.
  - `turn/practice_execution.py execute_practice()`/
    `execute_practice_group()`: RULES.AK -- "as soon as you assign your
    Heir his new skill levels, or improve any of his abilities by
    practice or experience, you lose the resurrection option." Both
    functions now clear `is_royal_heir` the instant Practice actually
    raises a skill or aptitude level (not merely attempted) for that
    leader -- the one real ability-improving mechanic this project has;
    "experience" has no separate skill-rise consumer anywhere to also
    clear it from, a documented, narrower gap.
  - **Deliberately deferred, confirmed with the user**: the player-
    facing order to actually create the new King (name/temper/skill
    distribution under RULES.AK [2.1]'s own 4-point allocation, its
    overlap-with-the-dead-King and doubled-Special-Aptitude
    constraints) -- a separate, later phase. Until then, an
    un-customized Heir simply holds the throne with zero Talents.
  - Non-breaking: 4 pre-existing tests updated for the new, intended
    behavior (a King's death no longer removes it from `state.leaders`
    outright) -- `test_challenge_execution.py`,
    `test_pursue_execution.py`, `test_plan_dispatch.py`,
    `test_turn_processor.py`, each now asserting the archived death
    plus the installed Heir instead of bare absence. 12 new tests: 4 in
    `tests/test_game_state.py` (`remove_leader()`'s own Heir
    installation, field-by-field, plus the Hero/kingless-King/unknown-
    id no-op cases); 4 in `tests/test_cast_execution.py` (Resurrection-
    on-Heir restores the exact King and his own `kingdom_id` regardless
    of which Kingdom casts it, co-location still enforced, fails
    without an archived King, credits the merit tally); 4 in
    `tests/test_practice_execution.py` (`is_royal_heir` clears on an
    actual rise, stays set when nothing rises, stays `False` for a
    non-Heir, and `execute_practice_group()` only clears it for
    whichever group member actually rose) -- 2960 passed total.

- **Phase 260**: completes King succession -- the player-
  facing act of actually creating a new King from the Phase 259 Royal
  Heir, `turn/succession.py create_king()`, sourced from RULES.AK
  [2.1] "Kings" (quoted in full in the module docstring) and [2.3]'s
  own "ALIGNMENT TABLE".
  - **Not a K1-decodable order, confirmed against the real Pascal
    `action` enum**: no ordinal for "create a King" exists anywhere in
    `CTBOTH.PAS`. RULES.AK's own [2.1] describes King creation as
    happening "at the start of the game," the same one-time act a
    Royal Heir's own creation now mirrors -- so `create_king()` is a
    directly-callable function, not a new `Maneuver`/`ActionCode` with
    a parser/decode layer, the same category `execute_practice_group()`
    already established for a call with no real order-file shape.
  - Validates RULES.AK's own 4-point allocation ("four abilities start
    at level 1, or 2 abilities at level two... can't assign more than
    2 points to any ability") and applies the automatic modifiers
    verbatim: +1 Melee/Archery/Sage for every King; a Divine King's own
    +1 White Magic and locked zero Necromancy skill/aptitude; an
    Undead King's own +1 Necromancy and locked zero White Magic
    skill/aptitude ("cannot start with any ability in a skill in which
    they have zero aptitude"). Aptitude is `skill + 2` (capped at 5)
    for every ability, with `turn/succession.py`'s own [2.3]-derived
    doubling rule for the two Magic/Special-Aptitude abilities of the
    King's own alignment (`ALIGNMENT_SPECIAL_ABILITIES`, transcribed
    from the Alignment Table's own Good/Druidic/Neutral/Pagan/Evil
    rows -- Divine/Undead read "None, None" there, confirming they
    don't get this doubling on top of their own separate override).
    **Documented, provable coincidence**: given the 0-2 player cap and
    at most one +1 bonus per ability, the doubling formula and the
    ordinary `+2` one are numerically identical for every value this
    module can ever actually produce -- kept as two separate functions
    anyway so the distinct [2.1]/[2.3] sourcing stays traceable, not a
    bug (see `_special_aptitude()`'s own docstring for the proof).
  - **Two genuinely unsourceable/unmodeled pieces, each confirmed with
    the user (project author) rather than guessed**: (1) "must assign
    at least 2 points to Talents the dead King had when he was
    created" can't be checked against true creation-time skills (never
    tracked separately from current, possibly-Practiced-up skills
    anywhere in this project) -- the dead King's own skill snapshot
    *at death* (`GameState.dead_leaders`, the same one Phase 259's
    Resurrection-on-Heir branch already reads) is used as the best
    available proxy instead, a documented simplification. (2) Sex
    (`models/sex.py`, new this phase, `LeaderState.sex`) was
    "confirmed absent" since Phases 195/217/230 for lack of a real
    consumer -- `create_king()` is that consumer now, confirmed with
    the user as also chosen at creation alongside name and temper.
  - Race and alignment are never re-chosen -- already true by
    construction, since the Royal Heir already carries the dead King's
    own values forward; `create_king()` never touches either field.
  - Non-breaking: full suite passed unchanged (2960 passed) before any
    new tests were written (a new module plus an all-`None`-default
    field touches nothing existing). 17 new tests in `tests/
    test_succession.py`: not-a-Royal-Heir and leader-not-found
    failures; the exact-4-points and max-2-per-ability validations;
    the overlap requirement (met, unmet, and skipped when no death
    snapshot exists -- the documented proxy in action); royal-training
    bonus stacking onto untouched abilities; race/alignment left
    untouched; the Divine/Undead skill-bonus-plus-locked-aptitude
    override in both directions, including rejecting an attempt to
    invest in the locked-out ability; the special-ability-alignment
    table's own five-alignment coverage; the special-vs-ordinary
    aptitude formulas' own documented numeric coincidence, checked
    directly -- 2977 passed total.

- **Phase 261**: closes Recruit's own long-flagged "ally
  Treat order precondition" gap (see Phase 15's/47's own notes above),
  sourced from RULES.AK [3.4]: "A character is allowed to recruit an
  army in a province belonging to his ally. The recruiter pays 1 gold
  to his ally for each recruited army... In order for you to Recruit
  in your ally's territory, he MUST issue a 'Treat' order with you
  (even though you may already be allied.)" -- being merely allied was
  never enough on its own.
  - **New `GameState.treat_permissions: set[tuple[int, int]]`**
    (directed `(owner_kingdom_id, recruiter_kingdom_id)` pairs) +
    `has_treat_permission()` helper, mirroring `allied_kingdoms`/
    `is_allied()`'s own raw-set-plus-helper shape (no wrapper "grant"
    method either, same convention). **No parser/decoder for a Treat
    order exists anywhere in this project** -- confirmed the same "no
    real order-file shape ever seen" category `turn/
    emperor_election.py`'s own docstring already established for Break
    Treaty and Call-For-Vote -- so the field is populated directly by
    the caller, not decoded from a move file. Not auto-cleared at a
    turn boundary, the same "caller's job" convention already governing
    `recruited_this_turn`/`ArmyState.movement_points`.
  - `turn/recruit_execution.py execute_recruit()`: when the target
    province is owned by an ally (`in_ally_territory`), the *entire*
    request is now blocked (`RecruitExecutionResult.treat_blocked`, no
    partial recruiting, no gold spent) unless the owner has granted
    this specific recruiter permission this turn -- a strict
    precondition on recruiting there at all, not merely on the ally-fee
    pricing that already existed. Recruiting in one's own territory is
    never gated by this check regardless of alliance status.
  - **Deliberately out of scope, documented not modeled**: the
    rulebook's separate "if you are recruiting in your former home
    province which is now your ally's province, you can recruit 4
    units" bonus (a different provision layered on top of the same
    paragraph) -- `is_home_province` only ever checks *current*
    ownership, so this specific case isn't distinguished from ordinary
    ally-territory recruiting. Also unaddressed, pre-existing and
    unrelated: this project still never blocks recruiting in a
    non-owned, non-allied (enemy/neutral) province at all -- the
    rulebook's own "You can never Recruit... in a non-player province"
    line stays unenforced, same as before this phase.
  - Non-breaking: full suite passed unchanged except for one
    pre-existing test that (correctly) assumed mere alliance was
    sufficient -- updated to grant `treat_permissions` explicitly,
    matching the new precondition (the same "expected, not a
    regression" pattern already established for Phase 259's own
    `remove_leader()` test updates). 5 new tests in `tests/
    test_recruit_execution.py`: granted permission still recruits and
    credits the ally as before; missing permission blocks the whole
    request with zero gold spent; the permission is directional (the
    recruiter granting himself doesn't count); recruiting in one's own
    territory is never gated; `has_treat_permission()`'s own direct
    coverage -- 2981 passed total.

- **Phase 262**: closes the last piece of the same RULES.AK
  [3.4] paragraph -- "Also, if you are recruiting in your former home
  province which is now your ally's province, you can recruit 4 units,
  and they will start as Average units" (flagged as deliberately out
  of scope in Phase 261's own note above).
  - `turn/recruit_execution.py` now splits what used to be a single
    "am I at my home province" check into two mutually exclusive
    flags: `is_home_province` (still self-owned -- ordinary 2-unit
    bonus, unchanged) and the new `is_former_home_province_now_allied`
    (location still matches `KingdomState.home_province`, which this
    project never reassigns after kingdom creation -- confirmed by
    grep -- but current ownership has passed to an ally). No new field
    needed: `home_province` already functions as the "original" home
    province the rulebook means, since nothing here ever updates it.
  - `turn/recruit.py`: new `FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT =
    4` constant; `recruit_limit()`/`resolve_recruit()` both gain an
    `is_former_home_province_now_allied` keyword (default `False`,
    every existing caller unaffected), checked before the ordinary
    home-province branch since it's the more specific case.
  - Still gated by Phase 261's own Treat-permission check -- this is
    still ally territory, just a more generous limit within it, not an
    exemption from the precondition.
  - Non-breaking: full suite passed unchanged (2981 passed) before any
    new tests were written. 7 new tests: `recruit_limit()`'s own
    4-unit case and its priority over the ordinary home-province flag,
    `resolve_recruit()`'s pass-through, and end-to-end coverage in
    `test_recruit_execution.py` (four units succeed with the bonus
    active, still blocked without Treat permission, and the ordinary
    self-owned home province stays capped at 2, not 4) -- 2987 passed
    total.

- **Phase 263**: completes Tactical Practice's own
  army-training mechanic (rulebook [6.1] "Types of Armies") -- Phase
  167 had implemented only 2 of the 5 upward Quality transitions
  (Green->Average 25%, Crack->Elite 0.2%) off an incomplete
  illustrative "e.g." quote in `turn/practice_decode.py`, leaving the
  other three unmodeled for lack of a source. RULES.AK's own [6.1]
  section (found this phase) gives the complete table directly,
  quoted in full in `turn/practice_execution.py`'s own docstring:
  Depleted->Green 100%, Green->Average 25%, Average->Veteran 5%,
  Veteran->Crack 1%, Crack->Elite 0.2%, each still gated on "an
  existing army of that [target] quality... there to train and
  inspire it."
  - `TACTICAL_TRAINING_CHANCE` now has all five entries.
    `execute_practice_tactical()`'s own gating logic (any *other* army
    under the same leader's command with a strictly higher *original*
    Quality tier, snapshotted before any rolls) needed **zero code
    changes** -- it was already generic over whatever tiers the chance
    table lists, so this phase is purely a data completion, not a
    redesign.
  - **Deliberately still out of scope, documented not conflated**:
    [6.1]'s own *separate* "Green and Depleted armies always improve
    to the next level at the end of a turn" rule -- an unconditional,
    turn-boundary rule with no Practice/inspiration precondition at
    all, confirmed by grep to have no existing turn-boundary hook in
    this project (same "no general per-turn reset mechanism yet"
    situation as `recruited_this_turn`). Also still out of scope:
    multi-leader army pooling ("if two leaders Practice Tactics
    together, their armies are pooled") -- unchanged from Phase 167.
  - Non-breaking: full suite passed unchanged (2987 passed) before any
    new tests were written (data-only change, existing GREEN/CRACK
    behavior untouched). One pre-existing test
    (`test_tactical_training_chance_only_has_green_and_crack`)
    correctly asserted the old, narrower table -- updated to assert
    all five entries, the same "expected, not a regression" pattern
    already established for prior phases' own test updates. 5 new
    tests: the newly-sourced Depleted/Average/Veteran transitions each
    training at their own chance, Elite (the one tier genuinely absent
    -- no next tier exists) staying untouched, and Depleted's own
    100% chance still requiring an inspiring army present -- 2991
    passed total.

- **Phase 264**: the last piece of Hire's own required-pay
  gap flagged since Phase 162's own note -- the "rare exception" bypass
  for an otherwise-refused wide alignment gap. Same manual passage
  Phase 162 already quoted, next sentence: "In rare occasioni un Re
  può assoldare Eroi con un Allineamento distante più di due posizioni
  dal proprio" ("On rare occasions a King CAN hire Heroes with an
  alignment more than two positions distant"). No percentage survives
  anywhere in the available source; asked the user directly
  (2026-07-28, same "ask when genuinely ambiguous" policy as Phase
  260's own succession mechanic) -- **15%**, user-specified.
  - `turn/hire_pay.py`: new `RARE_ALIGNMENT_EXCEPTION_CHANCE = 0.15`
    and `RARE_ALIGNMENT_EXCEPTION_PAY = 4` (the Hire action's own real
    offer ceiling, [3.5]: "a payment of 1-4 gold"), plus
    `roll_rare_alignment_exception(rng)`.
  - `turn/plan_dispatch.py _dispatch_hire()`: when `required_pay()`
    returns 5 (distance >= 3, previously an unconditional refusal),
    rolls the bypass once; on success the price drops to 4 instead of
    staying unreachable, so a King who actually offers the maximum can
    still succeed, otherwise the request is refused exactly as before.
    `HireExecutionResult.rare_alignment_exception` reports which path
    was taken. `_dispatch_hire()` gained an `rng` parameter (threaded
    from `dispatch_phase()`'s own existing one, its only call site).
  - A user-specified design constant, not a value transcribed from any
    Pascal or manual source -- documented as such in `hire_pay.py`'s
    own module docstring, not presented as a recovered rule.
  - Non-breaking: full suite passed unchanged (2991 passed) before any
    new tests were written -- the new roll only fires on the
    previously-always-refused `pay >= 5` path, and no existing test
    hit that path with an unscripted (non-deterministic) rng except
    one, fixed to script a deliberate failure so it keeps testing
    exactly what it always tested (see below). 7 new tests: the
    chance/pay constants, `roll_rare_alignment_exception()`'s own
    threshold in both directions (`hire_pay.py`), and end-to-end
    dispatch coverage (the rare exception succeeding at the offer
    ceiling and crediting only 4 gold, succeeding-but-still-refused
    when the offer stays below even the reduced price, and the
    pre-existing outright-refusal test now scripted to fail the roll
    deterministically rather than relying on luck) -- 2997 passed
    total.

- **Phase 265**: two stale claims found and corrected while
  hunting for the next well-scoped gap, plus the real fix each one was
  actually blocking. ASpy's own "Not yet implemented" note still said
  "no per-province tax-base model exists" -- false since Phase 222-224
  (`turn/tax_base.py`) -- and `turn/spy_table.py`'s own docstring still
  said the [4.33] Spy Table's "Margin of Error of Spy Reports" column
  had no resolver, when in fact `SpyReport.tax_estimate` (Phase 253)
  had already been passing the *exact* real tax yield straight through
  unperturbed the whole time -- a field literally named "estimate,"
  rendered through the real `_LSTax` template ("Approximate Taxation:
  #"), silently reporting the true value instead.
  - `turn/spy_table.py`: `margin_of_error_fraction(spy_skill)` exposes
    the table's own previously-unused column (0.70 at skill 0, down to
    0.15 at skill 4); `estimate_reported_value(true_value, spy_skill,
    rng)` perturbs a true integer by a uniform, symmetric,
    floor-at-0 offset within that margin. The percentages are the
    sourced part of [4.33]; **how a percentage becomes a perturbed
    number is this project's own documented design choice**, the same
    "no formula survives, only the shape is natural" category as
    `win_probability`'s own interpolation curve.
  - `turn/aspy_execution.py execute_aspy()`: now takes an `rng`
    parameter and reads the caster's own Spy skill (`_spy_skill_of()`,
    mirroring `turn/trail_execution.py`'s own identical helper) to
    perturb `tax_estimate` before it's returned -- `None` (never
    perturbed) whenever the base `ProvinceState.tax` was never
    recorded, unchanged from Phase 253.
  - **"Chance of Escaping Notice" (the table's third column) stays
    genuinely unmodeled**: a direct search of the available rulebook
    text found no described consequence of *being* noticed while
    spying anywhere, so there's nothing concrete to attach a roll's
    result to yet -- flagged, not guessed at.
  - Non-breaking: full suite passed unchanged except for one
    pre-existing test that (correctly) assumed the exact value was
    reported -- updated with a scripted rng landing the perturbation
    at exactly zero offset, the same "expected, not a regression"
    pattern already established this session. 10 new tests (5 in
    `test_spy_table.py` for the margin/perturbation functions
    themselves, 5 in `test_aspy_execution.py` for the wiring:
    zero-offset passthrough, maximum perturbation at Spy skill 0, the
    margin shrinking at Spy skill 4, the zero floor, and `None`
    staying unperturbed) -- 3011 passed total.

- **Phase 266**: closes Sage's "Discoveries" acquisition gap --
  `turn/merit_points.py`'s own module docstring had flagged this as "a
  materially larger, still-unscoped gap... this project has no
  acquisition mechanic for a `Discovery` at all," confirmed by an
  exhaustive search: Phase 171's own device-discovery roll
  (`PracticeExecutionResult.device_discovered`, [4.3.1]'s "5% chance
  per level") had never actually granted anything.
  - `models/game_state.py`: `KingdomState.discoveries: set[Discovery]`
    (new) -- matches `CTBOTH.PAS`'s own `dknow` array exactly (a
    per-kingdom, per-`discovery` boolean, confirmed via `REPORTS.PAS`'s
    own "Discoveries of the Sages" report loop and `RUMORS.PAS`'s own
    `dknow^[kng,discovery(...)]` reads), so a plain set needed no new
    abstraction.
  - `turn/practice_execution.py`: `_select_discovery_to_grant()` picks
    uniformly at random among the kingdom's not-yet-owned discoveries
    when the roll succeeds. *Which* specific Discovery gets granted has
    no surviving source anywhere -- the same "missing compiled unit"
    gap `turn/merit_points.py` already documents for this exact
    mechanic, and `models/discovery.py`'s own confirmed data (`discval`
    is a pure display-order key, not a difficulty/weight) gives no
    basis for weighting one of the 64 discoveries over another, so
    uniform selection is this project's own documented, unsourced
    design choice -- the same "no formula survives, only the shape is
    natural" category as `estimate_reported_value()`'s own uniform
    perturbation shape (Phase 265). `execute_practice()` now grants and
    records the outcome via a new `PracticeExecutionResult.
    discovery_granted: Discovery | None` field, left at `None`
    (honestly, not silently) for an independent Hero with no
    `kingdom_id` or a kingdom that has somehow already collected all 64.
  - `report/turn_report.py`: `render_sage_discovery()` (real extracted
    `PROSE/DISCOV.X` template, `SAY.PAS`'s own `_LDisc` report code) and
    `render_sage_no_discovery()` (`SAY.PAS`'s own `_LNoDisc` literal
    string) -- both standalone, not yet wired into `describe_practice()`
    's single-line-per-entry dispatch, since the device-discovery roll
    is independent of ("on top of, not instead of") the ordinary
    skill-rise roll `describe_practice()` already prioritizes between,
    and a call where both succeed would need an unsourced priority
    decision between two genuinely-narratable sourced templates --
    left to a real composer-wiring phase, the same "renderer exists,
    full wiring later" precedent already used for
    `render_wandering_encounter` (Phase 106) before its own eventual
    composer wiring.
  - **What's still not modeled**: the discovered device's *mechanical
    effect* (`models/discovery.py`'s own ability-bonus/anti-spell/
    revenue-bonus data isn't wired into actual gameplay yet -- a
    distinct, unstarted future phase, matching that module's own
    "vocabulary first, mechanics later" precedent), and the Chancellor
    Merit Point attribution (`MeritTally.discoveries_found_first`/
    `discoveries_via_espionage`, `turn/merit_points.py`) -- attributing
    "found first" needs a global first-inventor registry across every
    kingdom (the same shape as `Feature.discovered_by_kingdom`, Phase
    75/256) that this phase deliberately didn't invent alongside the
    acquisition mechanic itself, to keep the two concerns separate.
  - Non-breaking: full suite passed unchanged except for one
    pre-existing test that reached the newly-random `rng.choice()` call
    without scripting it -- updated with a `choice_indices` value, the
    same "expected, not a regression" pattern established this session
    for prior RNG-consuming additions. 13 new tests (kingdom starts with
    no discoveries; uniform selection excludes owned discoveries;
    exhausted-kingdom returns `None`; end-to-end grant/no-kingdom/
    already-complete coverage in `practice_execution.py`; both new
    renderers' branches in `turn_report.py`) -- 3021 passed total.

- **Between Phase 266 and 267 (docs-only)**: two stale docstring notes
  found and corrected, no behavior changes. `turn/search_execution.py`
  still claimed `models/item.py` was "a never-populated stub" and no
  treasure-instance model existed, contradicted a few lines below by
  its own `state.add_item()` call (Phase 140/242's own real fix, never
  backported to this docstring's own copy of the note).
  `models/feature.py` separately still called Rumor generation "out of
  scope," even though `turn/rumor.py` (Phase 243) and its
  `plan_dispatch.py` wiring already closed it. See commit `9a8637e`.

- **Phase 267**: closes ASpy's own espionage-Discovery gap,
  RULES.AK [3.14] (quoted in full in `turn/aspy_execution.py`'s own
  module docstring): "There is also a chance of finding out what Sage
  Discoveries the spied-on Kingdom has, and obtaining them for the use
  of your Kingdom... The chance for discovering an invention by spying
  is limited to twice the chance of discovery by Sages." A direct,
  well-sourced follow-up to Phase 266's own acquisition mechanic.
  - `turn/aspy_execution.py`: `_roll_espionage_discoveries()` rolls,
    independently, every `Discovery` the spied-on kingdom (the
    province's own `owner_kingdom_id`) has that the caster's own
    kingdom doesn't, at `2 * spy_skill * SAGE_DEVICE_DISCOVERY_CHANCE_
    PER_LEVEL` (capped at 100%) -- reusing `turn/practice_execution.py`'s
    own Phase 266 constant rather than a second copy of "5% per level,"
    since the rulebook here explicitly ties its own "twice" multiplier
    to that exact figure. Each success is granted directly to the
    caster's own kingdom and credits `MeritTally.
    discoveries_via_espionage` (rulebook page 51's own Chancellor
    formula, "+1 per Invention obtained via espionage" -- previously
    never incremented by anything). `SpyReport.discoveries_obtained:
    tuple[Discovery, ...]` records what was actually obtained. Espionage
    never targets the caster's own kingdom, and grants nothing for an
    independent Hero with no kingdom of their own -- the same "nowhere
    to grant a kingdom-level Discovery to" edge case Phase 266 already
    established.
  - **Two explicit, documented, unsourced design choices**: reading "a
    chance of finding out... and obtaining them" as one independent
    roll *per* Discovery rather than one roll unlocking the whole list
    (no source distinguishes the two readings; per-item independent
    rolls already match this project's own established shape,
    `turn/exploration.py discover_features()`); and not modeling the
    rulebook's own "common vs. obscure design" difficulty distinction,
    since `models/discovery.py`'s own confirmed data (`discval` is a
    pure display-order key) gives no basis for weighting one Discovery
    over another.
  - `models/game_state.py MeritTally`'s own docstring corrected in
    passing: it still claimed `monster_hp_neutralized` was "never
    incremented by any action," stale since Phase 258's own Fulfill
    wiring: closed alongside `discoveries_via_espionage`'s own new
    writer, per this session's established self-correction policy.
  - Non-breaking: full suite passed unchanged (3021 passed) before any
    new tests were written -- the new roll only fires when a spied-on
    kingdom actually owns a `Discovery` the caster's kingdom lacks,
    something no existing test's `GameState` ever set up. 10 new tests
    (`_roll_espionage_discoveries()`'s own same-kingdom/missing-kingdom/
    not-yet-owned-only/chance-formula/capped-at-100%-behavior directly,
    plus `execute_aspy()`'s end-to-end grant, merit credit, roll
    failure, unowned province, and no-candidates coverage) -- 3031
    passed total.

- **Phase 268**: closes the revenue-bonus half of the
  Discoveries-of-the-Sages gap `models/discovery.py`'s own module
  docstring left open since Phase 93 -- the real FINANCES report section
  now shows the kingdom's own actual held Discoveries and the
  `Inv_Bonus` line, both previously confirmed-absent for lack of any
  per-kingdom Discovery-tracking field (closed by Phase 266).
  - `models/enums.py`: `ABILITY_NAME` (new) -- `CTBOTH.PAS`'s own
    `anoun` array ("Tactics", "Marches", ... "Sageness"), a real,
    previously-unmodeled noun-form ability name table, distinct from
    `ABILITY_ABBREVIATION`'s two-letter codes.
  - `models/discovery.py`: `DISCOVERY_DISPLAY_VALUE` (new) --
    `CTBOTH.PAS`'s own `discval` const array, transcribed verbatim.
    Phase 93's own docstring had called this field's only use "that one
    print loop" and left it unmodeled; this phase is exactly that use.
    `discovery_effect_description()`/`describe_discovery_line()`/
    `sorted_kingdom_discoveries()` (new) reproduce REPORTS.PAS's own
    exact per-discovery report line ("+1 skill in <ability>" /
    "Anti-spell: <spell>" / "+X% revenue", name padded to a 25-character
    field, `discval`-descending order) -- real, quoted Pascal, not a
    project-original format.
  - `turn/tax_base.py`: `compute_invention_bonus_percent()` (new) --
    `Inv_Bonus(kng)`, the sum of every revenue-bonus Discovery a kingdom
    owns. REPORTS.PAS's own `IF Inv_Bonus(kng) > 0 THEN WRITELN(...
    Inv_Bonus(kng):3,'%')` confirms it prints as a bare percentage, not
    gold, so it stays additive to (never folded into)
    `compute_tax_base()`'s own return value -- the two remain separate
    report lines, matching the real source exactly.
  - `report/turn_report.py describe_finances_report()`: now renders the
    real "+Invention Bonus: X%" line (only when positive) and the real
    Discoveries-of-the-Sages list (falling back to the existing
    `_FINANCES_NONE_AT_PRESENT` only when the kingdom holds none).
    **Not modeled**: the `'(Received from player(s) #k1...'`
    parenthetical (`kexch[k1,kng]`) naming who a Discovery was received
    from -- this project tracks *that* a Discovery came from espionage
    (Phase 267) but not *from whom*, so there's nothing real to render
    for that suffix.
  - Non-breaking: full suite passed unchanged (3031 passed) before any
    new tests were written -- every existing FINANCES test's kingdom
    starts with an empty `discoveries` set, the same `_FINANCES_NONE_AT_
    PRESENT`/no-Invention-Bonus-line path as before. 18 new tests
    (`ABILITY_NAME` coverage/samples; `DISCOVERY_DISPLAY_VALUE`
    coverage/samples; `discovery_effect_description()` across all three
    effect categories; `describe_discovery_line()`'s padding at both a
    short and a boundary-length name; `sorted_kingdom_discoveries()`'s
    ordering and tie-breaking; `compute_invention_bonus_percent()`'s
    zero/mixed-discoveries cases; `describe_finances_report()`'s real
    discovery list, sort order, and Invention Bonus line shown/omitted)
    -- 3049 passed total.

- **Phase 269**: closes the ability-bonus half of the
  Discoveries-of-the-Sages gap `models/discovery.py`'s own module
  docstring left open since Phase 93 -- the user's explicit two-part
  request ("prima quelle che danno +1 ai talenti, poi quelle che
  bloccano o limitano gli incantesimi") starts here with the "+1 ai
  talenti" half; the anti-spell-ward half is the next phase.
  - `turn/discovery_effects.py` (new): `ability_bonus_from_discoveries()`
    sums how many of a kingdom's owned `fix0`-`fix9`/`wreck0`-`wreck9`
    Discoveries bonus a given `Ability` (0, 1, or 2 -- two Discoveries
    exist per bonused Ability, and REPORTS.PAS's own report loop prints
    each as an independent "+1 skill in..." line, so both stack rather
    than a flat non-stacking flag). `effective_skill_level()` adds that
    bonus to the leader's own stored `SkillTable` level (0 if unrecorded,
    the same pre-existing convention), capped at `MAX_SKILL_LEVEL` (9,
    `CTBOTH.PAS`'s own `skillrange`) -- see the module's own docstring
    for the full stacking/cap rationale and for the four sites
    deliberately left untouched (Practice's own roll, Use_MI's
    skill-raise write, succession's dead-King overlap check, the
    CHARACTERS report's raw skill column).
  - Wired `effective_skill_level()` into every real gameplay-outcome
    skill read this project has, replacing the raw
    `leader.skills.pair_for_ability(ability)[0]` read at each site:
    `turn/battle_orchestrator.py` (Druidic shortfall x2, Supreme
    Commander Tactical/Naval selection, `_commander_combatant()`'s own
    Melee read for Duel combat); `turn/cast_execution.py`
    (`_roll_cast_success()`'s own level read, `_caster_level()` --
    now takes `state` -- and its 5 call sites); `turn/
    challenge_execution.py` (`_leader_combatant()`'s own Melee read);
    `turn/merit_points.py` (`_skill_level_sum()` -- now takes `state`
    -- feeding Chancellor's Explorer/Spy/Sage sum and Priest's
    Druidic/White sum, threaded through `turn/office_holder.py`'s own
    two call sites); `turn/patrol_execution.py` (`_combat_skill_of()`/
    `_spy_skill_of()` -- both now take `state` -- and its own
    `_leader_combatant()`); `turn/pursue_execution.py`/`turn/
    trail_execution.py`/`turn/aspy_execution.py` (each module's own
    `_spy_skill_of()`, now taking `state`); `turn/search_execution.py`
    (`_leader_combatant()` -- now takes `state` -- plus the Mirror
    Image/Illusory Hero Sage+Illusion disbelief-bonus reads, the Cast
    tactic's caster level, Steal's Thief level, and Talk's Druid level,
    all already inside closures over `execute_search()`'s own `state`
    parameter, so only the read itself changed, not the signature).
  - Non-breaking: full suite passed unchanged (3049 passed) before any
    new tests were written -- every existing test's kingdom starts with
    an empty `discoveries` set, so `effective_skill_level()` degrades to
    the exact prior raw-skill read everywhere no test explicitly grants
    a Discovery. 4 pre-existing `test_merit_points.py` calls to
    `chancellor_merit_points()`/`priest_merit_points()` needed a
    `state` argument added for the new signature (a mechanical
    threading fix, not a behavior change).
  - 10 new tests: `turn/discovery_effects.py`'s own unit tests
    (zero/single/stacking bonus, independent-Hero and kingdom-not-found
    edge cases, stored-skill addition, and the `MAX_SKILL_LEVEL` cap),
    plus 3 targeted integration tests proving the wiring reaches real
    call sites (`_select_side_commander()`'s Tactical tiebreak now
    resolved by an owned `LAND_SHIP`; `chancellor_merit_points()`'s
    Explorer term now including an owned `COMPASS`) -- 3059 passed
    total.

- **Phase 270**: closes the anti-spell-ward half of the
  Discoveries-of-the-Sages gap `models/discovery.py`'s own module
  docstring left open since Phase 93 -- the second half of the user's
  explicit two-part request ("poi quelle che bloccano o limitano gli
  incantesimi"). Research first: the three SAY.PAS templates that
  seemed to promise one uniform block/reduce mechanism (`_SCounter`/
  `_SComCtr`/`_SComRed`) have no recoverable trigger logic anywhere in
  the surviving 14 `.PAS` files (a confirmed dead end, the same
  category as Phase 137's Merit Point globals) -- but `Discovery.txt`
  (already the confirmed-authoritative source for this project's whole
  Discovery catalog since Phase 93) turned out to describe each of the
  16 `bild10`-`bild43` anti-spell Discoveries with its own distinct,
  fully-specified mechanical override, not a shared formula. Of the 16:
  4 target spells this project has never implemented (Hand of Death,
  Fireball, Psychic Blast, Invisibility) and stay blocked for that
  reason alone; 4 more describe a real Discovery.txt effect but the
  *base* mechanic they'd modify has no consumer in this codebase to
  begin with (Flood's own land-units-trapped effect, Clairvoyance's own
  info feed, Illusory Terrain's own "who believes it," and Oratory's
  own per-battle "33% chance affected," which would need a brand-new
  per-army boosted-by-Oratory-this-turn flag this project doesn't
  track) -- each documented at its own call site rather than guessed
  into existence. The remaining 7 are wired:
  - **Cast-time, checked against the *defended* side's own Kingdom**
    (`turn/cast_execution.py`): Hidden Tattoos neutralizes Kill_Enemy
    (the target survives; the "sick, practices randomly" secondary
    effect isn't modeled -- no sickness/forced-Practice mechanic
    exists to hook it into); Penicillin replaces Plague's destroy roll
    with a flat 50% quality-downgrade chance (`apply_plague_exposure()`
    -- same shape as the pre-existing immunity branch, just
    unconditional and at a fixed rate); Giant Fan does the same for
    Tornado; Reinforced Concrete replaces Earthquake's -100% tax
    modifier with a flat 3-gold reduction (new `ProvinceState.
    earthquake_flat_reduction` field, consumed by `turn/tax_base.py
    province_tax_yield()`, since the existing `tax_modifier_percent`
    field is percent-only and can't express a flat amount). A new
    `CastExecutionResult.discovery_defended: Discovery | None` field
    flags when any of these fired, without disturbing `applied`'s own
    existing "the spell was cast" meaning.
  - **Cast-time, checked against the *acting* Kingdom**
    (`turn/exploration.py discover_features()`): Hand-Held Radar
    bypasses `Feature.magically_hidden` entirely for the searching
    Kingdom's own rolls.
  - **Battle-time, checked against the *opposing* side's Kingdom(s)**
    (`turn/battle_orchestrator.py _build_battle_units()`, new
    `opponent_kingdom_ids` parameter resolved once by `fight_battle()`
    from each side's own army roster): Osteopathic Germ Warfare reduces
    a Skeletal Army unit (`ArmyState.is_skeletal`) by one quality level
    for that battle's strength computation only (`turn/cast_execution.py
    quality_one_level_down()`, promoted from private to shared);
    Observation Balloons reduces Phantasmal Armies' own strength bonus
    from 15%/level to 5%/level (`turn/strength.py
    phantasmal_armies_multiplier()`'s new `bonus_per_level` parameter,
    threaded through `compute_effective_strength()`'s new
    `phantasmal_armies_bonus_per_level` parameter). Both are genuinely
    battle-time effects, not Cast-time interceptions -- Discovery.txt's
    own wording ("in any battle which the Kingdom conducts") ties them
    to whichever battle the Discovery-owning Kingdom is actually
    fighting, not to when the opposing spell was originally cast.
  - Non-breaking: full suite passed unchanged (3059 passed) before any
    new tests were written -- every existing test's kingdom starts with
    an empty `discoveries` set and no army is ever `is_skeletal` by
    default, so every new check degrades to its exact prior behavior.
  - 9 new tests across `test_cast_execution.py` (Hidden Tattoos,
    Giant Fan, Reinforced Concrete, Penicillin), `test_exploration.py`
    (Hand-Held Radar), `test_battle_orchestrator.py` (Observation
    Balloons, Osteopathic Germ Warfare), and `test_tax_base.py`
    (`earthquake_flat_reduction`'s own flat-reduction and floor-at-zero
    cases) -- 3068 passed total.

- **Phase 271**: unblocks the Gran Cancelliere / Chancellor's
  own Discovery-attribution Merit Point terms, the "materially larger,
  still-unscoped gap" `turn/merit_points.py`'s own Phase 137/256 note
  flagged as needing a global first-inventor registry across every
  kingdom, now that Phase 266 gave this project a real Discovery-
  acquisition mechanic to attribute. **User-specified scoring rule**
  (2026-07-29), explicitly requested to replace the rulebook's own flat
  "+2 per Invention found first" figure: the world's first hero/King
  ever to discover a given Discovery scores **3** points; every later,
  independent discoverer of that same Discovery scores **2** (the
  rulebook itself awards nothing at all for a non-first personal
  discovery -- this project's own owner chose to score both cases).
  - `models/game_state.py`: `GameState.discoveries_first_found_by:
    dict[Discovery, int]` (new) -- a global, permanent, write-once
    registry (Discovery -> the Kingdom that discovered it first),
    the same "one shared, world-wide fact" shape `Feature.
    discovered_by_kingdom`'s own per-instance registry doesn't need
    (many Kingdoms can each independently know about the same
    Feature; a Discovery has exactly one true first inventor,
    game-wide). `MeritTally.discoveries_found_not_first: int` (new)
    joins the existing `discoveries_found_first` -- one counter per
    outcome, so `chancellor_merit_points()` can apply the 3/2 weights
    directly rather than re-deriving "was this first" from stored data.
  - `turn/practice_execution.py execute_practice()`'s own SAGE branch:
    right after a successful device-discovery roll adds a new
    `Discovery` to the practicing leader's own Kingdom, checks
    `discoveries_first_found_by` -- absent means this Kingdom is the
    world's first (registry written, `discoveries_found_first`
    credited); present means some other Kingdom already got there
    first (registry left untouched, `discoveries_found_not_first`
    credited instead). Espionage-copied ownership (`turn/
    aspy_execution.py`, Phase 267) never corrupts this check: the
    registry only ever asks "does *any* Kingdom already know this,"
    regardless of how they came to know it.
  - `turn/merit_points.py chancellor_merit_points()`: `3 *
    discoveries_found_first + 2 * discoveries_found_not_first`,
    replacing the old, never-populated `2 * discoveries_found_first`
    term.
  - Docs-only, in passing: `turn/practice_execution.py`'s own module
    docstring updated to stop saying Discovery mechanical effects are
    "a distinct, unstarted future phase" -- Phases 269/270 already
    wired both halves.
  - Non-breaking: full suite passed unchanged except one pre-existing
    test (`test_chancellor_merit_points_adds_discovery_tally_terms`)
    that asserted the old `2 * discoveries_found_first` formula --
    updated to the new 3/2 weights, a mechanical fix for the
    intentional formula change, not a regression.
  - 2 new tests in `test_practice_execution.py` (world-first discoverer
    credited 3 points and registers itself; a second, independent
    discoverer of the same already-registered Discovery credited 2
    points, registry entry left unchanged) -- 3070 passed total.

- **Phase 272**: implements rulebook [8.4] Scientific
  Treaties, previously listed as blocked ("ordine cartaceo, non
  parsificato da questo progetto" -- unparseable paper order). The
  underlying "Treat" order is still unparseable, same as ever, but
  Phase 261 already solved the identical problem for [3.4]'s own half
  of the same order (Recruit's ally-territory permission gate):
  `GameState.treat_permissions` is populated directly by the caller,
  not decoded from a move file. [8.4] reuses that exact field rather
  than inventing a second permission model -- a *mutual* Treat order is
  just `(a, b)` and `(b, a)` both present in `treat_permissions` the
  same gameturn.
  - New `turn/scientific_treaty.py`, `execute_scientific_treaties()`:
    for every mutual-Treat pair of currently-Allied Kingdoms in contact
    (some province each owns is hex-adjacent, via `turn/movement.py
    is_adjacent()`, or a leader from one is physically located inside a
    province the other owns), each side gives away its own
    highest-priority Discovery the other doesn't already hold --
    computed independently per direction, so a lopsided exchange (only
    one side has anything new) falls out naturally rather than needing
    a special case, matching the rulebook's own "If only one of the
    Kingdoms has a secret unknown to the other, one secret will still
    be given away."
  - **Exchange priority ("the most military-oriented ones" / "the order
    of their priority for scientific exchanges")** reuses `models/
    discovery.py sorted_kingdom_discoveries()` (Phase 268) rather than
    inventing an unsourced military-ness ranking: the rulebook text
    explicitly says the turn report's own Discoveries-of-the-Sages
    ordering (descending `DISCOVERY_DISPLAY_VALUE`, the real, sourced
    `discval` field) *is* the scientific-exchange priority ordering.
  - **Two explicitly documented, confirmed-absent-data limitations**
    (not silent guesses -- see the new module's own docstring for the
    full reasoning): (1) "have become Allies on a previous gameturn" is
    read as *current* `is_allied()` status only, since this project has
    no alliance-formation timestamp anywhere to check duration against
    -- `allied_kingdoms` is, like `treat_permissions`, entirely
    caller-populated with no in-project writer; (2) "the exchange takes
    place after finances are computed" has no equivalent hook inside
    `turn/turn_processor.py run_turn()`, since this project never
    applies revenue as a mutating turn-processor step (`turn/
    tax_base.py`'s formulas are computed on demand for report
    rendering only) -- `execute_scientific_treaties()` is therefore a
    standalone resolver the caller invokes directly, the same
    "caller's job" convention `treat_permissions` itself already
    established.
  - **No Merit Point credit**: the rulebook's own printed Chancellor
    table (`turn/merit_points.py`) lists three specific Discovery-
    attribution sources -- personal invention (first or not) and
    "obtained via espionage" -- and Scientific Treaty exchange is none
    of the three, so `MeritTally.discoveries_via_espionage` and
    `GameState.discoveries_first_found_by` are both deliberately left
    untouched by a Treaty-received Discovery.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (3079 passed once the new tests below were included).
  - 9 new tests in `test_scientific_treaty.py`: mutual-Treat exchange
    between allied, adjacent Kingdoms; no exchange when the Treat order
    isn't mutual; no exchange without alliance; no exchange without
    contact; leader-presence-alone satisfying contact; the lopsided
    one-direction-only exchange; highest-`DISCOVERY_DISPLAY_VALUE`
    priority selection; no result recorded when neither side has
    anything new; and confirmation that neither `discoveries_via_
    espionage` nor `discoveries_first_found_by` are touched -- 3079
    passed total.

- **Phase 273**: extends Fire Arrow into Challenge, Pursue and
  Duel -- previously only Search (Phase 170) actually resolved a
  `Maneuver.SHOOT` tactic as a real Fire Arrow duel; Challenge and
  Pursue only ever consulted it to decide whether combat-acceptance
  restrictions applied (`has_combat_intent`), then always fought a
  Melee duel regardless, and Duel's own `_maybe_fight_duel()` docstring
  explicitly said "always Melee, since no Encounter Plan data exists
  anywhere in this project" -- a real, previously undocumented gap for
  the first two, and a documented-but-now-closable limitation for the
  third.
  - New `turn/encounter.py resolve_encounter_combat()`: walks an
    Encounter Plan's own tactic list in order (rulebook [5.10]/[5.2]/
    [3.16] -- "All rules listed under the Encounter action apply to
    Pursuit encounters," and Duel's own [7.1] cross-references [5.10]
    by name), the same "Fire Arrow first if listed, fall through to
    Melee once shots exhaust or the list runs out" rule Search's own
    Phase 170/178 corrections already established -- reused directly
    rather than re-derived, since it's one shared rulebook mechanic.
  - `turn/challenge_execution.py`/`turn/pursue_execution.py`:
    `_leader_combatant()` now also reads `Ability.ARCHERY` into
    `Combatant.archery_skill` (previously left at the default 0, which
    would have made Fire Arrow a guaranteed no-op even once wired), and
    both call `resolve_encounter_combat()` with the real decoded
    `request.tactics` instead of always calling `resolve_melee_duel()`
    directly.
  - `turn/battle_orchestrator.py`: `_commander_combatant()` reads
    `Ability.ARCHERY` too. `_maybe_fight_duel()`/`fight_battle()` gain
    an optional `duel_maneuvers: list[Maneuver] | None = None` parameter
    -- `None` (every existing caller) reproduces the exact prior
    always-Melee behavior and RNG consumption unchanged; a caller who
    does have real Special Encounter Plan data for a Duel can now supply
    it. This project still has no parser/decoder for a standing,
    per-leader Special Encounter Plan (distinct from the one-off
    tactics a CHALLENGE/PURSUE order itself carries) -- the same "no
    real order-file shape ever seen" category as Treat/Break
    Treaty/Call-For-Vote -- so `duel_maneuvers` stays caller-supplied
    rather than auto-derived, matching `treat_permissions`'s own
    established convention.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (3088 passed once the new tests below were included) --
    confirming no existing test exercised a `SHOOT`-tactic Challenge or
    Pursue encounter, and the `duel_maneuvers` default preserves every
    existing Duel test's own RNG consumption exactly.
  - 9 new tests: 5 for `resolve_encounter_combat()` itself (Fire-Arrow-
    then-fallback ordering, empty-list default, Melee-terminates-before-
    a-later-SHOOT-entry, skipping unrelated maneuvers), 1 each for
    Challenge's and Pursue's own SHOOT-tactic wiring (a high-Archery,
    zero-Melee attacker reliably beats a zero-Archery, high-Melee
    defender -- impossible under the old always-Melee behavior), and 2
    for `battle_orchestrator.py` (`_commander_combatant` reads real
    Archery skill; `_maybe_fight_duel` resolves Fire Arrow first when
    `duel_maneuvers` is supplied) -- 3088 passed total.

- **Phase 274**: wires Use_MI and Scout as real Search
  Encounter Plan tactics ([5.1]/[3.11] and [5.8] respectively); Give
  stays deliberately unwired (re-confirmed directly by the user, project
  author -- see below). This closes a stale scoping note: `turn/use_mi_
  execution.py`'s own `GameState.items`/`TREASURE_WAND_SPELL` machinery
  (Phase 140/141) had already closed the "no magic-item-instance ->
  spell-effect mapping" gap `search_execution.py`'s own module docstring
  used to justify skipping Use_MI -- the note was simply never updated.
  Scout was re-examined directly against RULES.AK [5.8] after a prior
  session's own note calling it "'non esiste' as a distinct mechanic,
  served by Talk instead" turned out to be wrong; the user (project
  author) confirmed it's real and distinct, and supplied two Pascal
  PROSE reference files (`PCOND.X2`, `POWMSG.X2`) describing the
  Scout-explorable Power-condition mechanic.
  - **Use_MI [US]**: `tactic.sub_object` is a magic-item-instance id
    (`turn/search_decode.py`'s own docstring), resolved through the same
    `GameState.items` registry Phase 140/141 already established. Only
    the 20 spell-casting wands are combat-relevant here (a Skill Book
    mid-fight isn't a "cast"); an unowned/missing/non-wand/empty item is
    a documented no-op, same as `execute_use_mi()`'s own precedent. New
    `_resolve_use_mi_tactic()` reuses `_resolve_cast_tactic()`'s own
    13-spell dispatch directly via a new `forced_level` parameter
    (`SEARCH_USE_MI_WAND_SKILL_LEVEL = 2`, TREASAB.X2's own "at skill-2"
    label on every wand) instead of duplicating any spell-effect code --
    [3.11]'s "a spell cast from a magic item is automatically
    successful" skips `resolve_personal_combat_spell_cast()`'s own roll
    entirely. A charge is spent only when the wand's own spell was
    actually a modeled Personal-Combat spell that passed every
    precondition (the new `cast_attempt_applied` flag), not on a
    rejected target or an unmodeled spell -- the same "spend only on a
    genuine cast" rule `execute_use_mi()` already follows.
  - **Scout [SC]**: resolved as a genuine post-processing step
    (`_apply_scout()`, called once by a new thin `execute_search()`
    wrapper after the renamed `_resolve_search_encounter()` settles its
    own outcome) rather than at Scout's own position in the tactic walk
    -- [5.8] states position never matters and Scout always resolves
    last, which a single post-hoc pass honors far more cleanly than
    threading a hook through this module's dozen-plus return sites. Only
    the discovery-*level* effect is modeled
    (`Feature.discovered_by_kingdom`, real since Phase 75/242): a plan
    that "calls for Talking, Fulfilling or Attacking" (Melee/Fire Arrow)
    is a guaranteed full reveal (level 3); a bare Steal is the
    rulebook's own named 67% chance, a bare Flee its own named 33%
    (level 2, "a magic-power hint is known," on a miss); every other
    combination (Cast-only, Beg-only, a bare Scout) matches neither the
    guaranteed branch nor either named exception, so it's genuinely
    unresolved by the source -- no discovery-level change at all, not a
    guessed-at percentage. Never downgrades an already-higher level. A
    dead leader can't Scout (skipped outright); a kingdomless
    (independent-Hero) leader has nowhere to record a per-kingdom
    discovery, also skipped. What Scout would actually *reveal* (the
    Special's own real content) stays unmodeled: no `Feature` in this
    project is ever assigned a `Power`/`PowerCondition`
    (`models/power.py`'s own vocabulary has no real instance anywhere)
    -- confirmed directly with the user, who chose this narrower scope
    explicitly. New `SearchExecutionResult.scout_orders_given` records
    how many Scout tactics the plan actually listed, regardless of
    outcome -- `PCOND.X2` (user-supplied) confirms two Scout orders on
    the same feature is this game's own explicit consent mechanism for 3
    of `PowerCondition`'s 6 real conditions (`PayUp`/`DrainSkill`/
    `DrainCourage`), a sourced fact recorded honestly even though
    nothing yet consumes it (no Feature carries a Power to consent to in
    the first place).
  - **Give**: re-confirmed unwired, no code change -- the user's own
    prior note stands as correct ("exactly one real use, passing an item
    to another Hero or King, never to a monster; Search's own target is
    always the guardian monster").
  - Non-breaking: full suite passed unchanged before any new tests were
    added (3088, matching Phase 273's own final count).
  - 19 new tests: 8 for Use_MI (missing/unowned/non-wand/no-charge
    items all fall through to the plan's own next tactic; a Wand of
    Charm is automatically successful and spends exactly one charge,
    regardless of the caster's own real, unrelated skill level; a Wand
    of Oratory -- a real item whose spell isn't one of the 13 modeled
    Personal-Combat effects -- is a no-op that spends no charge; a Wand
    of Hand of Death kills the guardian instantly), 11 for Scout (no
    Scout tactic leaves the feature untouched; multiple Scout tactics
    are all counted; the guaranteed Talk/Fulfill/Melee/Shoot branch; a
    dead leader is skipped but still counted; the rulebook's own two
    named 33%/67% Steal and Flee percentages, both directions each; a
    plan matching neither the guaranteed branch nor either named
    exception is genuinely unresolved; an already-fully-known feature is
    never downgraded by a failed re-scout; a kingdomless leader is a
    no-op) -- 3107 passed total.

- **Phase 275**: closes, with a fresh declaration-level audit
  (not a re-read of prior notes), four still-open turn-report gaps: FINANCES'
  "Expected Expenses" line and its Evilking/ThiefPrince gold-bonus notes,
  PROVINCES' Tax column/Recruiting-Types columns, and ARMIES' "Modified
  Quality" column. Docs-only, no behavior change -- every one of these
  lines was already confirmed absent by earlier phases; this phase
  re-verifies that with a stronger, falsifiable method and records the
  result as a single canonical, dated closure so a future session doesn't
  need to re-derive it (as this session nearly did, after an automated
  survey pass repeated two already-corrected stale claims from a much
  earlier session -- monster combat stats coverage and Use_MI item
  resolution -- both independently re-verified false in this same phase).
  - Searched all 14 raw `.PAS` files under `HostAK/TP`/`HostAK/MS` (13
    with real content; `COMPANY.PAS` is a 5-byte stub) for a `function`/
    `procedure` **declaration** of `ACost`, `LCost`, `Qual_Modfr`, and
    `Mod_PAT`, and a `var`/array **declaration** of `ptax`/`pt2` -- zero
    matches for any of the six. Every real occurrence in `REPORTS.PAS`/
    `RUMORS.PAS` only ever *calls* or *reads* them, confirming they live
    exclusively in the missing main turn-processor / the lost
    `AKGEN.EXE` world-generator.
  - New "Phase 275" addendum in `report/turn_report.py
    compose_letter_report()`'s own docstring is the single canonical
    citation for this audit; `describe_finances_report()`,
    `describe_provinces_report()`, `describe_armies_report()`, and
    `turn/recruit.py`'s own module docstring each got a short, dated
    pointer back to it rather than a duplicated re-explanation.
  - The Evilking/ThiefPrince gold-bonus notes are a different shape from
    the other four (the `Office` members themselves are real,
    `models/office.py`) -- what's confirmed absent is any hook tracking a
    running per-kingdom gold total tied to holding either office.
  - None of these five is expected to become sourceable later; a future
    phase could still choose a project-original substitute (the same
    kind of user-confirmed design choice `turn/tax_base.py
    compute_tax_base()` made for `Tax_Base` itself), but that's a new
    design decision, not a continuation of this search.
  - Non-breaking: full suite passed unchanged both before and after (no
    code behavior changed, only docstrings) -- 3107 passed both times.
    No new tests (pure documentation).

- **Phase 276**: wires the FINANCES "Expected Expenses" line
  for real, reopening the "not expected to become sourceable" call
  Phase 275 made about `ACost`/`LCost` one day earlier -- the user
  supplied real generated `SE3__T*.K*` turn-report samples (2026-07-29)
  that let both components be verified directly against actual game
  output instead of only cited from the lost Pascal source.
  - New `turn/expenses.py`: `compute_army_maintenance()` sums
    `ARMY_TABLE[army_type].pay` (RULES.AK [6.3]) across a kingdom's own
    Hired armies -- verified **exact, zero discrepancy**, against four
    independent real sample files (`SE3__T0.K2`/`K3`/`K5`/`T1.K2`).
    `compute_leader_maintenance()` reuses `turn/hire_pay.py
    required_pay()` (Phase 162/163/264, the Hire-pricing formula
    already built from the real manual text) for the recurring per-turn
    figure ([3.5]: "The Hero is paid when he signs up and at the end of
    each gameturn") -- verified against 3 of 4 real Heroes exactly, with
    one known mismatch (a Pagan Dwarf Hero under a Human Neutral King)
    that looks like the still-missing race term [3.5] itself names but
    `required_pay()` never added (built before `LeaderState.race`
    existed). The King and any Valhalla visitor
    (`models/valhalla.py VALHALLA_VISITOR_LEADER_ID`) always contribute
    0, checked explicitly rather than left to the formula. On the
    user's own explicit direction: wired now as-is, the race gap
    documented rather than blocking the whole line.
  - `report/turn_report.py describe_finances_report()` now renders
    "Expected Expenses" via `compute_expected_expenses()`; 3 existing
    tests updated for the new line.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (3107, matching Phase 275's own final count, once the 3
    pre-existing FINANCES-shape tests were updated for the new line).
  - 10 new tests in `test_expenses.py`: army maintenance summing,
    ignoring mercenary and other-kingdoms' armies; leader maintenance
    for a King (0), an ordinary Hero (`required_pay()`), multiple
    Heroes summed, a Valhalla visitor (0), and other-kingdoms' leaders
    ignored; and one full real-sample regression test reproducing
    `SE3__T1.K2`'s own "Expected Expenses: 15" exactly (13 gold across
    six armies + 2 gold across two Heroes) -- 3117 passed total.

- **Phase 277**: adds `Office.EVIL_KING` ("King of Pain") and
  `Office.THIEF_PRINCE` ("Prince of Thieves") to the real Merit Point
  Rank contest, and wires the two revenue-boosting bonuses they grant
  into the FINANCES section -- sourced from a reference file the user
  supplied directly (`CARICHE E ABILITÀ.txt`, 2026-07-29, the 8-major-office
  + these 2 titles' exact English perk text and Italian scoring formulas),
  scoped narrowly to just these two offices on the user's own explicit
  choice; the file's further ~13 race/alignment fanaticism titles are
  deliberately deferred to a future phase.
  - `models/game_state.py MeritTally` gains 4 new fields feeding the two
    formulas (`monsters_killed_in_realm_province`,
    `successful_thief_tactics`, `gold_stolen`, `magic_items_stolen`) --
    all currently unpopulated, no writer yet, matching this project's
    established "field exists, writer comes later" convention for every
    other Merit Point tally counter.
  - `turn/merit_points.py`: `evilking_merit_points()` -- King of Pain is
    King-only and Evil-Kingdom-only (returns 0 otherwise), summing
    Tax_Base + Necromancy skill + Thief skill + the two new
    monster/thief tally counters. `thiefprince_merit_points()` -- Prince
    of Thieves has no eligibility gate (a Hero can win it too), summing
    Thief skill + `gold_stolen` + `5 * magic_items_stolen`.
  - `turn/office_holder.py`: `RANKED_OFFICES`/`ALL_OFFICES` extended from
    7/8 to 9/10 real offices; `_leader_merit_points()` dispatches the two
    new formulas through the same generic Rank-contest loop every other
    non-Emperor office already uses -- no special-casing needed beyond
    the formulas' own built-in eligibility gates.
  - `report/turn_report.py describe_finances_report()`: two new
    conditional lines, "(Including +5 Black Knights)" /
    "(Including +10 Thieves Guild)", rendered right after "Gold in
    treasury" and before "Expected Revenues" whenever this Kingdom's own
    King/Hero currently holds the matching office -- confirmed against 5
    real `SE3__T*.K1` samples (the note starts appearing the turn *after*
    the title is actually earned, e.g. `SE3__T8.K1` vs. `SE3__T7.K1`),
    correcting an initial assumption (based only on nearby Pascal line
    numbers) that the notes rendered after "Expected Expenses" instead.
    `describe_imperial_office_report()`'s own table already iterates
    `ALL_OFFICES` generically, so it now automatically gains "King of
    Pain"/"Prince of Thieves" rows too -- confirmed as a real table row
    by the `SE3__T10.K1` sample, not a bug to suppress.
  - Non-breaking: full suite passed unchanged before any new tests were
    added, once 4 pre-existing tests were updated for the 7->9/8->10
    office counts and the two new "None at present" table rows -- 3117
    passed.
  - 16 new tests: `evilking_merit_points()`/`thiefprince_merit_points()`
    eligibility and scoring in `test_merit_points.py`; EVIL_KING/
    THIEF_PRINCE actually resolving through the Rank contest in
    `test_office_holder.py`; and the two FINANCES bonus notes' presence,
    absence, kingdom-scoping, King-vs-Hero-holder crediting, and
    relative ordering in `test_turn_report.py` -- 3133 passed total.

- **Phase 278**: closes the PROVINCES "Tax" and "Recruiting
  Types" column gaps `describe_provinces_report()`'s own docstring had
  called "confirmed absent" since Phase 220/275 -- that audit only ever
  established no Pascal *formula* survives for `ptax`/`Mod_PAT` (still
  true), not that the real per-province *data* was unrecoverable. It
  was: `parser/gw_world.py`/`gw_world_bridge.py` (Phase 222-224) already
  bridge `ptax` from a real `GW3` world file, and this phase decodes
  that same file's own previously-unparsed line 3 (`Mod_PAT(px,py,0)`/
  `Mod_PAT(px,py,1)`) the same way.
  - `parser/gw_world.py`: cross-referenced 701 real "PROVINCES" table
    rows (every `SE3__T*.K*` turn with a matching `GW3__T<n>` file, by
    province name) against that world file's own line 3 -- a
    **100% exact, zero-conflict decode** for all 19 distinct ordinals
    observed. New `MOD_PAT_ORDINAL_TO_ARMY_TYPE` maps ordinals 0-14
    directly onto this project's own `ArmyType` enum order; ordinal 15
    is the real "no second recruit type" sentinel (`None`); 16-19
    (`MERMEN`/`ENTS`/`TROLLS`/`WEREBEASTS`) are each one ordinal higher
    than this project's own enum places them, revealing the real Pascal
    enum has one more member (the sentinel) than this project's own
    model does. `GWProvinceRecord` gains `recruit_type_1`/
    `recruit_type_2: ArmyType | None`.
  - `models/game_state.py ProvinceState` gains matching
    `recruit_type_1`/`recruit_type_2` fields (`None` until bridged, the
    same convention `tax` already uses); `parser/gw_world_bridge.py
    bridge_gw_world_provinces()` copies both straight across --
    already-decoded data, no new logic needed there.
  - `report/turn_report.py describe_provinces_report()`: appends
    `", Tax {yield}"` (via `turn/tax_base.py province_tax_yield()`, so
    Scar Terrain/Bless/Earthquake modifiers apply here too) and
    `", Recruits {type1}[/{type2}]"` (via `ARMY_TYPE_DESIGNATION`) to
    each owned province's line whenever known; both omitted entirely
    for a province whose `GameState` was never bridged from a real world
    file -- no data isn't a true zero. `compose_letter_report()`'s own
    Phase 275 audit note updated to stop calling `ptax`/`Mod_PAT`
    "confirmed absent" (only `Qual_Modfr`/`pt2` still are).
  - Non-breaking: full suite passed unchanged before any new tests were
    added -- 3136 passed (3133 plus 3 new `gw_world` parser tests
    written alongside the decode itself, before the report-composer
    change).
  - 7 new tests in `test_turn_report.py`: Tax shown/omitted, Tax
    reflecting Scar Terrain reduction (confirming it renders via
    `province_tax_yield()` not the raw field), both Recruiting Types
    shown, a single type shown when the second is the real "None" case,
    Recruits omitted when unbridged, and both columns together in the
    real table's own order -- 3143 passed total.

- **Phase 279**: closes the ARMIES report's "Modified Quality"
  column (`Qual_Modfr`) gap `describe_armies_report()`'s own docstring
  had called "confirmed absent" since Phase 220/275 -- true only of a
  Pascal *formula*. The user's own quoted rulebook text named five real
  modifiers, and every one of them turned out to already be a sourced,
  implemented mechanic elsewhere in this project (home-province bonus
  and desert-without-camels penalty from Phase 35, Druidic-ability
  shortfall from Phase 41/42) or a genuinely new but fully-sourced one
  (the four race-matching legendary leadership items, real names already
  catalogued in `models/treasure.py TREASURE_NAME` since Phase 77) --
  the same "formula lost, inputs sourced" category Phase 277/278 both
  closed before it.
  - New `turn/army_quality.py compute_army_modified_quality()`: combines
    all five modifiers via `turn/strength.py modified_quality()`'s own
    single-pass clamp (its new `race_item_bonus` parameter, default 0 so
    every existing battle-strength call site is unaffected -- this
    bonus is wired into the report column only, not into real combat
    strength, a deliberately narrower scope matching the user's own
    "reconstruct the report column" framing). `RACE_LEADERSHIP_TREASURE`
    maps Human/Elf/Dwarf/Orc to Excalibur/Bow of the Elven Kings/Axe of
    the Dwarven Lords/Scimitar of Orc Mastery -- real names, no
    combat-quality wiring existed for them before this phase (only an
    unrelated Merit Point bonus, `merit_points.py LEGENDARY_ITEM_BONUS_
    TREASURES`). Unlike Druidic ability, this bonus has no King-
    substitution carve-out for an unled army -- the user's own rules
    name only the army's own commanding Hero or King.
  - `turn/battle_orchestrator.py`: `druidic_shortfall_for()`/`king_
    druidic_shortfall_for()`/`find_king_of_kingdom()` made public
    (dropped their leading underscore) so `army_quality.py` can reuse
    the exact same commander/King-substitution resolution outside of an
    active battle, instead of re-deriving it a second time -- no logic
    changed, only visibility.
  - `report/turn_report.py describe_armies_report()`: renders a second
    `Quality` name, "Modified {X}", next to the existing normal one,
    matching the real table's own two-column shape; its own "confirmed
    absent" docstring bullet removed. `compose_letter_report()`'s Phase
    275 audit note updated the same way Phase 278's was -- `Qual_Modfr`
    moved from "still confirmed absent" to the closed list, leaving only
    `pt2`.
  - Non-breaking: full suite passed unchanged before any new tests were
    added, once 6 pre-existing tests were updated for the new column --
    every one of them happened to place its own test army in the
    kingdom's own home province, so all six needed a "Modified {X}"
    clause added even though none of them intended to exercise the new
    feature -- 3143 passed.
  - 14 new tests: `compute_army_modified_quality()`'s five modifiers
    (home province, desert-with/without camels, led and King-substituted
    Druidic shortfall, race-item bonus and its race-matching requirement,
    ceiling/floor clamping, an unregistered province) in
    `test_army_quality.py`; `modified_quality()`'s own new
    `race_item_bonus` parameter, including the single-pass-clamp-vs-two-
    step distinction, in `test_strength.py` -- 3157 passed total.

- **Phase 280**: closes the CHARACTERS report's own "Pay"
  column (`Ini`/`LCost(ldr,kng)`) gap -- reopening Phase 275's "confirmed
  absent" call the same way as Phase 276/278/279 before it: no Pascal
  *formula* for `LCost` survives (still true), but this project already
  built one from the real manual text for the Hire-time price
  (`turn/hire_pay.py required_pay()`, Phase 162/163/264), and FINANCES'
  own "Expected Expenses" line already reuses it for the identical
  recurring figure (Phase 276) -- CHARACTERS' own "Pay" column is the
  same figure a third time, not a new formula.
  - `turn/expenses.py`: extracted `leader_pay(leader, king)` out of
    `compute_leader_maintenance()`'s own inline loop body -- 0 for the
    King himself or a Valhalla visitor, `required_pay()` otherwise --
    so both the FINANCES sum and the new CHARACTERS column share the
    identical exclusion logic instead of duplicating it.
  - `report/turn_report.py describe_characters_report()`: appends
    `", Pay {n}"` to each leader's own first line, right after Race,
    matching the real table's own column order. Confirmed against
    `SE3__T1.K2`'s own real CHARACTERS table: Bradipo I (King) -- 0;
    Adele -- 1; Indra -- 1, all reproduced exactly. `compose_letter_
    report()`'s own CHARACTERS bullet and Phase 275 audit note both
    updated the same way as Phase 276/278/279's own closures.
  - Non-breaking: full suite passed unchanged before any new tests were
    added, once 4 pre-existing tests were updated for the new column
    (every one of them happened to already exercise a leader whose real
    Pay value could be computed from already-set-up alignment/temper
    data) -- 3157 passed.
  - 6 new tests: `leader_pay()`'s own King/Valhalla-visitor exclusions,
    the real-sample Adele/Indra values, and the no-King permissive
    default in `test_expenses.py`; the CHARACTERS report's own real-
    sample row values and an alignment-distance-driven Pay difference in
    `test_turn_report.py` -- 3163 passed total.

- **Phase 281**: closes the ARMIES report's own Skeletal-Army
  "Skel <designation>" display gap -- a *different* kind of unblock from
  Phase 276/278/279/280's own "formula lost, inputs sourced" pattern:
  here the real formula (`REPORTS.PAS:986-992`, the `Doit` procedure
  nested inside `Rep_Armies` itself -- confirmed by direct read, the
  exact site `turn/army_naming.py make_army_display_name()` was already
  built from in Phase 236) was never missing, and neither was the data
  (`ArmyState.is_skeletal`, Phase 236, set by every Skeletal_Army cast).
  `describe_armies_report()`'s own docstring simply had a stale claim --
  "`ArmyState` has no equivalent per-army undead/skeletal flag" -- left
  over from before Phase 236 added that very flag, and the branch was
  never wired to read it.
  - `report/turn_report.py describe_armies_report()`: the per-army
    designation now branches on `army.is_skeletal`, exactly matching the
    real `Doit` procedure's own `IF astate[an] = Zomboid THEN
    Concat(s,' Skel ',atdesig[...]) ELSE Concat(s,' ',atname[...])` --
    `ARMY_TYPE_DESIGNATION` (not `ARMY_TYPE_NAME`) prefixed with "Skel "
    for a skeletal army, the ordinary `ARMY_TYPE_NAME` otherwise. Only
    the branch logic is reused, not `make_army_display_name()`'s own
    ordinal-number prefix -- this composer's "province -- leader:
    designation" line never rendered a per-army ordinal to begin with, a
    distinct, already-documented formatting choice not reopened here.
    Cross-checked against the same real sample `turn/army_naming.py`'s
    own docstring already cites (`SE3__T0.K1:135`, "108th Skel Bowmen").
    Both this function's own docstring and the module-level docstring's
    own "not wired into any function below" note are corrected.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (no existing test army had `is_skeletal=True`, so the new
    branch was dormant against every prior fixture) -- 3163 passed.
  - 2 new tests: a skeletal Lt Cavalry army rendering "Skel Lt Cav" (the
    clearest real case, since `Lt Cav` genuinely diverges from `Light
    Cavalry`) and a non-skeletal Lt Cavalry army still rendering "Light
    Cavalry", both in `test_turn_report.py` -- 3165 passed total.

- **Phase 282**: implements Island provinces (PROVINCES'
  `pt2`, the "(...Island)" Type 2-terrain parenthetical) -- a genuinely
  different kind of closure from every other Phase-275-audit identifier
  before it (Phase 276/278/279/280/281): `pt2` has no real Pascal
  formula AND no real-file data source of any kind, so what renders now
  is **project-original**, implemented per the user's own explicit
  domain knowledge (2026-07-29), not recovered from any source -- an
  optional Super AK variant rule (games up to 24 players): a province
  that's half Sea, half its own land terrain, where armies fight at a
  blended half-land/half-Sea strength; overflight-air units (Dragons,
  Eagles) are exempt, the user's own words ("le province volanti...
  non hanno nessuna variazione").
  - `models/game_state.py`: new `ProvinceState.is_island: bool = False`
    field -- the province's own land `terrain` is unchanged (an Island
    is never literally `Terrain.SEA`; that would just be an ordinary Sea
    province), this is a Sea-half overlay flag on top of it.
  - `turn/strength.py compute_effective_strength()`: new `is_island`
    parameter. Extracts the terrain-dependent portion of the pipeline
    (base strength, race/army-type terrain bonuses, adverse-terrain
    halving, Whales' off-Sea zero-strength override) into a new
    `_terrain_strength()` helper, called twice (once against the
    province's own land terrain, once against `Terrain.SEA`) and
    averaged when `is_island=True` and the army isn't an overflight-air
    unit (`models/army_type.py OVERFLIGHT_AIR`); a single ordinary pass
    otherwise. One useful emergent consequence, not special-cased
    separately: a Whale unit on an Island nets exactly half its normal
    Sea strength (0, the off-Sea override, averaged with its full Sea
    value).
  - `turn/battle_orchestrator.py`: `fight_battle()` resolves
    `province.is_island` once and threads it through both
    `_build_battle_units()` calls and both `_apply_pursuit()` calls (the
    same province-level fact `terrain` already gets threaded through),
    so a battle's own strength and a clean-swept loser's own pursuit-
    chase strength both honor it.
  - `turn/island_provinces.py` (NEW): `apply_island_provinces(state,
    island_count, rng)` -- the world-creation-time setup helper the user
    asked for: "optional, decided at world creation... exact island
    count instead of an exact land-province count." This project has no
    full terrain-layout world generator at all (`turn/world_generation.py`
    only ever populates *features* onto already-existing provinces; the
    real `AKGEN.EXE` is compiled-only, no source survives), so this
    marks an exact count of already-populated land provinces as Islands
    -- chosen uniformly at random (sorted first for determinism), not a
    percentage. Raises `ValueError` on a negative or over-large count,
    the same explicit-refusal style `turn/recruit_execution.py`'s own
    per-turn-limit checks already use.
  - `report/turn_report.py describe_provinces_report()`: appends
    `" (Island)"` right after the terrain name when `province.is_island`.
    `compose_letter_report()`'s own Phase 275 audit note updated to
    describe this Phase 282 closure accurately (project-original, not
    sourced) rather than leaving the stale "not expected to become
    sourceable" prediction in place.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (`is_island` defaults to `False` everywhere, and no existing
    fixture set `ProvinceState.is_island`) -- 3165 passed.
  - 16 new tests: the land/Sea averaging, the Whales-half-strength
    emergent case, the overflight-air exemption, and the `is_island=False`
    default in `test_strength.py`; `_build_battle_units()`'s own
    `is_island` threading and a `fight_battle()` integration test proving
    the province's own flag reaches real battle strength in
    `test_battle_orchestrator.py`; the exact-count picker, its Sea/
    NO_TERRAIN/already-island exclusions, its `ValueError` refusals, and
    its seeded determinism in the new `test_island_provinces.py`; the
    "(Island)" parenthetical rendering (present and absent) in
    `test_turn_report.py` -- 3181 passed total.

- **Phase 283**: corrects the Island-province terrain
  parenthetical's own rendered text, `" (Island)"` -> `" (Sea)"`,
  against the user's own real PROVINCES report example (2026-07-29):
  ```
  Province            Tax   Race   Terrain  Expl%     Type 1     Type 2
  Mongu                10   Human   Jungle (Sea) 100%     Legion     Fleet
  ```
  This example also resolves a separate ambiguity from Phase 282's own
  framing ("Type 1 is the land part, Type 2 is Island"): the real
  table's own **"Type 1"/"Type 2" column pair is the Recruiting Types**
  (`Mod_PAT`, e.g. `"Legion"`/`"Fleet"`) -- already rendered here since
  Phase 278 as `", Recruits X/Y"` -- not terrain at all. The terrain-
  level Type 1 (land)/Type 2 (Sea) split the user was originally
  describing lives entirely inside the real table's own single
  `Terrain` column instead (`"Jungle (Sea)"`), matching this composer's
  own one-line-per-province shape -- no new column needed, only the
  parenthetical's own wording.
  - `report/turn_report.py describe_provinces_report()`: `terrain_name
    += " (Island)"` -> `" (Sea)"`; `ProvinceState.is_island` itself,
    `turn/strength.py`'s `is_island` parameter, and `turn/island_
    provinces.py` are all unchanged -- this is purely a display-text
    correction, not a mechanics or data-model change. Both docstrings
    (this function's own and the module driver's ten-section summary)
    updated to match, plus a new paragraph distinguishing the real
    Type 1/Type 2 *columns* from the terrain-level Type 1/Type 2
    *concept*.
  - Non-breaking: full suite passed unchanged before the one existing
    test's own expected string was updated -- 3181 passed (the fix
    only changes what one already-passing assertion expects, not new
    coverage).
  - 0 new tests: the existing Phase 282 Island-parenthetical test
    (`test_describe_provinces_report_shows_island_parenthetical`) was
    updated in place to expect `"Plain (Sea)"` instead of `"Plain
    (Island)"`, still 3181 passed total.

- **Phase 284**: implements the Temper Table's own Melee-combat
  mechanics -- Furia, Intimidazione, Slancio, Schivare -- against the
  real "TABELLA DEI TEMPERAMENTI" (`Regolamento AK.txt`, ~lines 3392-3428).
  `turn/encounter.py`'s own module docstring had stated (since Phase 48)
  that this project had no `Temper` model anywhere; that claim was
  already stale -- `Temper` (Phase 82) and `LeaderState.temper` (Phase
  139) both existed, just never wired into combat. This phase closes
  that gap:
  ```
  Temperamento    Effetti Speciali        Fuga           Rifiuto
  Berserk         Furia, Intimidazione    Mai            Mai
  Coraggioso      Slancio                 (probabilita)  Mai
  Cauto           Schivare                (rischio)      1-50%
  Codardo         Implorare pieta         (morte)        51-100%
  ```
  Only the four *melee-math* effects (Furia/Intimidazione/Slancio/
  Schivare) are modeled this phase; flee probability, refusal-to-Meet,
  and Cowardly's own "Implorare pietà" are a different rulebook
  mechanic (decision/tactic-selection, not melee math) and are
  explicitly left for a future phase. Fire Arrow is untouched -- its
  hit chance is governed solely by Archery skill per [5.2], and the
  Temper Table is never invoked there.
  - `turn/encounter.py`: new constants
    `BERSERK_FURY_BONUS_HIT_POINTS_RANGE = (1, 4)`,
    `BERSERK_INTIMIDATION_HIT_CHANCE_REDUCTION` (Brave -5%, Cautious
    -10%, Cowardly -15%), `BRAVE_MOMENTUM_HIT_CHANCE_BONUS = 0.10`,
    `CAUTIOUS_DODGE_HIT_CHANCE_REDUCTION = 0.10`. New
    `Combatant.offensive_hit_multiplier: float = 1.0` field -- the
    first *attacker*-side hit-chance multiplier this module has
    needed (existing `defensive_hit_multiplier`, from Phase 209's Holy
    Symbol/Invisibility, only ever multiplied the *opponent's* chance
    to land a hit). New `Combatant.temper: Temper | None = None` field.
    New `berserk_fury_bonus_hit_points(rng)` and
    `apply_temper_melee_setup(a, b, rng)` functions; the latter is
    called as the very first line of `resolve_melee_duel()`, before
    the round loop, and mutates each side's `hit_points`,
    `defensive_hit_multiplier`, and `offensive_hit_multiplier` in
    place per its own Temper (and its opponent's, for Intimidazione).
    `resolve_melee_duel()`'s hit-chance multiplier changed from
    `defender.defensive_hit_multiplier` to `attacker.
    offensive_hit_multiplier * defender.defensive_hit_multiplier`,
    following the same multiplicative convention `holy_symbol_hit_
    chance()` already established (Phase 209) rather than flat
    percentage-point subtraction. Applying Intimidazione as a
    multiplier on the Berserk's own `defensive_hit_multiplier` (keyed
    by the *opponent's* Temper) composes automatically with every
    pre-existing defensive multiplier without any special-casing.
  - `turn/challenge_execution.py`, `turn/patrol_execution.py`, `turn/
    pursue_execution.py`, `turn/search_execution.py`, `turn/battle_
    orchestrator.py`: each module's own `_leader_combatant`/
    `_commander_combatant` helper now passes `temper=leader.temper`
    (or `None` for a Druid-substituted/garrison commander with no real
    leader) into the `Combatant` it builds -- the same "duplicated
    per-consumer lookup" precedent these five functions already follow
    (see each one's own docstring), not refactored into a shared
    helper.
  - Non-breaking: full suite passed unchanged before any new tests
    were added (`offensive_hit_multiplier` defaults to `1.0` and
    `temper` defaults to `None` everywhere, so `apply_temper_melee_
    setup()` is a no-op for every existing fixture) -- 3181 passed.
  - 17 new tests: the Temper Table's own constants, `berserk_fury_
    bonus_hit_points()`'s range, and every `apply_temper_melee_setup()`
    branch (Furia's bonus hit points, Intimidazione keyed by the
    opponent's own Temper including the Berserk-vs-Berserk no-op case,
    Slancio's offense-only boost, Schivare's defense-only reduction,
    the no-Temper no-op, and both sides' multipliers composing
    independently) plus `resolve_melee_duel()`'s own wiring (setup
    runs before combat via the `max_rounds=0` isolation trick, and the
    attacker's own offensive multiplier is actually read) in `test_
    encounter.py`; one wiring-confirmation test per consumer
    (`_leader_combatant`/`_commander_combatant` reads the real
    `LeaderState.temper`, and the garrison-commander carve-out stays
    `None`) across `test_challenge_execution.py`, `test_patrol_
    execution.py`, `test_pursue_execution.py`, `test_search_
    execution.py`, and `test_battle_orchestrator.py` -- 3198 passed
    total.

- **Phase 285**: wires the race-matching legendary leadership
  item's +1 quality bonus into real combat strength -- Phase 279 had
  already computed it for the ARMIES report's own "Modified Quality"
  column (`turn/army_quality.py compute_army_modified_quality()`), but
  `turn/strength.py compute_effective_strength()`'s own real
  `_build_battle_units` caller in `battle_orchestrator.py` never passed
  it through, exactly as that function's own docstring had explicitly
  flagged since Phase 279. Closed by threading the same
  `race_item_bonus` parameter one level further.
  - `models/treasure.py`: the `RACE_LEADERSHIP_TREASURE` table (Excalibur
    for Human, Bow of the Elven Kings for Elf, Axe of the Dwarven Lords
    for Dwarf, Scimitar of Orc Mastery for Orc -- no entry for any
    non-humanoid race, unchanged from Phase 279) moved here from `turn/
    army_quality.py`, its original single owner, so `turn/battle_
    orchestrator.py` can share it too without a circular import
    (`army_quality.py` itself already imports from `battle_
    orchestrator.py`).
  - `turn/strength.py compute_effective_strength()`: new `race_item_
    bonus: int = 0` parameter, passed straight through to `modified_
    quality()`'s own parameter of the same name (unchanged since Phase
    279). Module docstring and `modified_quality()`'s own docstring
    both updated to drop the "report column only" caveat.
  - `turn/battle_orchestrator.py _build_battle_units()`: computes
    `race_item_bonus` per unit the same way `compute_army_modified_
    quality()` already does -- a *led* army (`commanded_by` is not
    `None`) whose commander holds the item matching this side's own
    `kingdom.race` gets +1, checked via `state.items_held_by()`. Same
    "commander only, no King-substitution carve-out for an unled army"
    rule the ARMIES report's own column already established (the
    user's rulebook text names only the army's own commanding Hero or
    King). Fully deterministic, no `rng` involved.
  - `turn/army_quality.py`: its own `compute_army_modified_quality()`
    is unchanged -- it still independently computes the same bonus
    against `army.location` for the peacetime report column, rather
    than calling the battle path. Only its import of
    `RACE_LEADERSHIP_TREASURE` moved to the new shared location; its
    module docstring's "Scope, deliberately narrow" section rewritten
    to point at this phase instead of claiming report-only forever.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (`race_item_bonus` defaults to 0 everywhere) -- 3198 passed.
  - 4 new tests: `compute_effective_strength()`'s own `race_item_bonus`
    passthrough in `test_strength.py`; `_build_battle_units()`'s three
    wiring cases (matching item boosts a led army, a wrong-race item is
    ignored, an unled army gets nothing) in `test_battle_orchestrator.py`
    -- 3202 passed total. `test_army_quality.py`'s existing
    `RACE_LEADERSHIP_TREASURE` coverage test updated to import from its
    new home rather than duplicated.

- **Phase 286**: wires the two Flee flee-chance bonuses
  `turn/search_execution.py`'s own Phase 169 docstring had explicitly
  deferred -- the Weak-Temperament (Cautious/Cowardly) and Invisibility
  "+30% chance to flee" bonuses on top of rulebook [5.6]'s own base
  20%/50%/80% `FLEE_CHANCE` roll.
  ```
  (NOVITA') I personaggi Cauti hanno il 30% in più di possibilità di
  fuggire.                                              -- [5.6]
  ```
  The rulebook names only **Cautious** for this bonus; the user (project
  author) confirmed extending it to **Cowardly** too is a deliberate,
  project-original design choice (Cowardly already sits at the far end
  of the Temper Table's own flee-inclination spectrum), documented as
  exactly that rather than conflated with the sourced text.
  - `turn/encounter.py`: new `Combatant.is_invisible: bool = False`
    field -- a separate explicit flag rather than inferring invisibility
    from `defensive_hit_multiplier`'s own value (fragile once more than
    one multiplier composes), read by this phase's own flee-chance
    helper. Default `False` leaves every pre-Phase-286 caller unaffected.
  - `turn/search_execution.py`: new `WEAK_TEMPER_FLEE_CHANCE_BONUS = 0.30`
    (`Temper.CAUTIOUS`/`Temper.COWARDLY`) and `INVISIBILITY_FLEE_CHANCE_
    BONUS = 0.30` constants, and a new `effective_flee_chance(base_chance,
    *, temper, is_invisible)` helper: both bonuses are **additive
    percentage points** on the base `FLEE_CHANCE` (not a multiplicative
    scaling of it) -- "30% in più" ("30% more") reads as a flat
    probability addition the same way the rulebook's own three base
    percentages are flat, the same "no sourced stacking formula, pick
    the plain reading" category `exploration_advantage_multiplier()`'s
    own docstring already uses. Both bonuses can stack together, clamped
    to 1.0 (a probability can't exceed certainty). The `Spell.
    INVISIBILITY` branch now also sets `caster.is_invisible = True`
    alongside its existing `defensive_hit_multiplier` mutation. Both real
    `FLEE_CHANCE[stats.speed]` roll sites -- the main `Maneuver.FLEE`
    tactic and `AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER`'s own reuse of
    the same mechanic -- now route through `effective_flee_chance()`
    instead of the bare table lookup.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (`is_invisible` defaults to `False`, and `effective_flee_
    chance()` returns the unmodified base chance for every existing
    caller with no Temper/no invisibility) -- 3202 passed.
  - 12 new tests: `effective_flee_chance()`'s own no-bonus/Cautious/
    Cowardly/Brave-and-Berserk-unaffected/Invisibility/stacking-and-
    clamping cases; wiring confirmations that a Cautious or Cowardly
    leader's `Maneuver.FLEE` roll succeeds where the unboosted chance
    would fail, that Brave gets no bonus and falls through to Melee,
    that casting Invisibility sets `is_invisible` and that a subsequent
    Flee gets its own bonus, and that Augur Combat's flee-when-cast-later
    branch reads the same Cowardly bonus -- all in `test_search_
    execution.py` -- 3214 passed total.

- **Phase 287**: renders the per-leader treasure list in the
  CHARACTERS report -- `describe_characters_report()`'s own docstring
  had explicitly left this out (`List_Treas(ldr,false)`, "a deliberately
  narrower scope for this phase, not a data gap"), even though Phase
  140's item-ownership registry could already answer it directly.
  - `report/turn_report.py describe_characters_report()`: a third line
    per leader, `state.items_held_by(leader.leader_id)` joined via
    `TREASURE_NAME` -- the same "join `TREASURE_NAME` per held item"
    pattern the trail report's own treasure-list rendering already
    established (Phase 117). Omitted entirely (no third line at all,
    not an empty "Items:" line) for a leader holding nothing -- there's
    nothing to itemize, not missing data. The docstring's own "what this
    deliberately does NOT reproduce" list updated: the treasure list
    moves out of that list into a new closed-item note; the magic-item-
    ownership *tick marks* on the skill line (`NT_Owned`, a finer-grained
    change needing `TREASURE_ABILITY_ITEM`'s own positional mapping)
    stay explicitly out of scope, unchanged.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (a leader holding nothing renders exactly as before -- no new
    line) -- 3214 passed.
  - 3 new tests in `test_turn_report.py`: multiple held items joined in
    one line, the line's total absence for an item-less leader, and that
    each leader's own line only reflects items owned by that same
    `leader_id` -- 3217 passed total.

- **Phase 288**: implements the PROVINCES report's real
  fixed-width columns and tax-tier grouping -- both previously left as
  a documented "presentation choice, not a missing data gap", the same
  way every other section composer in this module treats fixed-width
  formatting. Closed directly from `REPORTS.PAS Rep_Provs` (~lines
  404-459), which this project located and read in full this phase
  (`C:\Users\Andrea\Desktop\Gioco\HostAK\TP\REPORTS.PAS`):
  ```
  FOR tt:= 11 DOWNTO 0 DO FOR px:= left TO right DO FOR py:= top TO bottom DO
      IF powner[px,py] = kng THEN IF Min(11,ptax[px,py] +
          8*ord((px = bornx[kng]) and (py = borny[kng]))) = tt THEN BEGIN
        ...
        WRITELN(playfile,pname^[px,py],'':20-Length(pname^[px,py]),ptax[px,py]:3,
          rname[Mod_PRace(px,py)]:8,tername[pterr[px,py]]:9,pex[px,py]:6,'%',
          atdesig[Mod_PAT(px,py,0)]:11,atdesig[Mod_PAT(px,py,1)]:11);
  ```
  Reading this directly corrected two things this project previously
  had wrong or unconfirmed, both from an earlier paraphrase written
  before this project had direct source access:
  - **No per-tier subheading exists.** The column header prints exactly
    once, guarded by a `none`-flag shared across the whole province
    list, not reset per tier -- "grouped by descending tax tier" means
    only that row *order* follows the `tt` loop (11 downto 0); it
    produces no visible boundary text. This module's own docstring had
    said "subheadings per tier," which turns out to have been an
    overstatement.
  - **The tier formula** is `min(11, tax + 8)` *only for whichever
    province is the kingdom's own home province* -- every other owned
    province's tier is just its own tax (still capped at 11).
  - `report/turn_report.py`: new `_PROVINCES_COLUMN_CAPTION`/
    `_PROVINCES_COLUMN_HEADER` (the real, verbatim two-line header,
    printed once); new `_province_tax_tier(province, coord, kingdom)`
    implementing the formula above (`province_tax_yield()` returning
    `None` falls back to 0 for this sort-order computation only, not an
    assertion that the real tax is zero); `describe_provinces_report()`
    now sorts by `(-tier, x, y)` instead of plain coordinate, and
    renders each province as one real fixed-width row (name left-
    justified in 20 chars; Tax/Race/Terrain/Expl%/Type-1/Type-2 right-
    justified in 3/8/9/6/11/11 -- Python's own `ljust`/`rjust` never
    truncate a longer value either, matching Pascal's `:N` overflow
    behavior, relevant for an Island's own `"Jungle (Sea)"` terrain
    string exceeding its 9-char field) instead of the previous free-text
    `"Name -- Race, Terrain, N% explored, ..."` line.
  - Non-breaking check **skipped for the rewrite itself** (this is an
    intentional behavior/format change, not an additive one -- the
    entire point was to replace the old free-text rendering), but the
    full suite was run immediately after the rewrite to catch every
    site the format change touched.
  - All 16 pre-existing `describe_provinces_report()` tests rewritten
    against the new fixed-width format via a new `_province_row()` test
    helper (mirroring the real row-formatting logic for readable
    expected-value construction); 2 `compose_letter_report()` integration
    tests' own embedded PROVINCES fixture lines updated to match. 3 new
    tests: the column caption/header render exactly once, tax-tier
    ordering beats coordinate ordering (a low-tax province that's the
    kingdom's own home province sorts ahead of a higher-tax non-home
    province), and the home-province tier bonus caps at 11 rather than
    overflowing past it -- 3220 passed total.

- **Phase 289**: completes the Personal-Combat spell engine's
  own spell coverage -- a broader gap survey had mischaracterized this
  project's "spell engine for personal combat" as largely unbuilt.
  Re-checked directly: `turn/search_execution.py _resolve_cast_tactic()`
  has dispatched 15 of `turn/encounter.py`'s own 16 documented Personal-
  Combat spell mechanics since Phase 238 (the ten base spells, Charm's
  combat form, and four of the five secret spells). Only Words of
  Healing (`Spell.HEAL`, Phase 200's own addendum) was missing -- a
  plain oversight, not a design gap: every secret spell added from Phase
  202 onward got its own dispatch branch the same phase its primitives
  landed, but Words of Healing's primitives (Phase 200) predate that
  pattern (established Phase 202) and nobody circled back.
  - `turn/search_execution.py`: new `WORDS_OF_HEALING_KNOWN_ABILITY_
    LEVEL = 5` (same secret-spell skill-5+ gate as Illusory Hero's own
    `ILLUS_HERO_KNOWN_ABILITY_LEVEL`); `_resolve_cast_tactic()` gained a
    `Spell.HEAL` ability-lookup branch (`Ability.WHITE`) and effect
    branch calling `words_of_healing_heal()` outright once the gate and
    the cast roll both pass -- self-only, no target interaction. A
    monster caster's own healing ceiling reuses the already-captured
    `monster_starting_hit_points` (Phase 255's own Merit Points variable,
    not re-derived); a leader caster's is `CHARACTER_HIT_POINTS`. Every
    stale "13-spell"/"outside the 13 named above" count in this module's
    own docstrings corrected to 16.
  - `turn/encounter.py`: Words of Healing's own Phase 200 addendum
    updated with a "wired as of Phase 289" note, matching the pattern
    every other spell's addendum already carries.
  - `turn/cast_execution.py`: the module docstring's stale "the 10
    Personal-Combat-only spells... none of these ten can be attempted
    without building that engine first" claim (accurate through Phase
    208, false since Phase 209-238 actually built that engine one spell
    at a time inside `search_execution.py`) corrected via an addendum
    note, per this project's own "correct via addendum, don't rewrite
    history" convention -- the original stale paragraph is left verbatim
    below the note as the historical record.
  - **What's still genuinely open, precisely re-scoped** (`turn/
    search_execution.py`'s own new Phase 289 addendum): (1) spell
    disruption (`spell_disruption_chance()`, Phase 179) is still never
    rolled anywhere in this walk -- not an oversight like Words of
    Healing, but structurally unwireable at this walk's own granularity
    (it needs "hits taken this round," but tactics here resolve as whole
    self-contained duels, not a round-by-round loop a CAST could
    interleave into) -- this project's largest remaining piece of
    unbuilt personal-combat machinery, not a small addition; (2) this
    dispatch is still Search-only -- `turn/challenge_execution.py`/
    `turn/pursue_execution.py` still resolve personal combat via Melee/
    Fire Arrow alone, with no CAST support, and generalizing
    `_resolve_cast_tactic()` into a shared cross-consumer function is
    real, scoped follow-up work, not attempted this same phase.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (the new `Spell.HEAL` branch is additive -- every existing
    spell's own branch and eligibility gate is untouched) -- 3220
    passed.
  - 3 new tests in `test_search_execution.py`: a damaged leader casting
    Words of Healing is healed to `CHARACTER_HIT_POINTS` before its next
    Melee round; the skill-4 White Magic gate blocks the cast roll
    entirely (mirroring Illusory Hero's own gate test); a monster caster
    (via a patched `MONSTER_MAGIC_ABILITIES` entry) heals to its own
    `monster_starting_hit_points` rather than the character constant --
    3223 passed total.

- **Phase 290**: wires Personal-Combat spells into Challenge
  and Pursue, closing the gap Phase 289's own addendum flagged --
  `turn/challenge_execution.py`/`turn/pursue_execution.py` previously
  only resolved Melee/Fire Arrow, silently skipping every `CAST` tactic
  even though `ChallengeRequest.tactics`/`PursueRequest.tactics` already
  decode a `CAST` entry's own spell id (`SearchTactic.sub_object`).
  - `turn/challenge_execution.py`: new `_resolve_personal_combat_cast()`
    -- re-derived branch-for-branch from `turn/search_execution.py
    _resolve_cast_tactic()`'s own leader-target ("target is not a
    monster") branches, since an Encounter/Pursue opponent is *always*
    another leader, never a monster. Every monster-species classifier
    (Undead/Anti-Holy/Mechanical/Animal-Intelligence/submarine/flying)
    collapses to a plain `target_leader.alignment` check or an
    unconditional default (Mirror-Image/Illusory Hero's own opponent
    tier defaults to High Human; Lava Pool's own escape-chance speed
    defaults to Medium) -- Gate Demon still summons a real monster
    `Combatant` for the demon itself via `MONSTER_COMBAT_STATS`/
    `roll_gate_demon_type()`, unrelated to opponent classification. New
    `resolve_challenge_combat()` walks the full `SearchTactic` list
    (not just each entry's own `.maneuver`, unlike `turn/encounter.py
    resolve_encounter_combat()`), dispatching `CAST` in addition to the
    existing Fire-Arrow-then-Melee walk, with `_consume_bonus_attacks()`
    resolving any Psychic-Blast/Ice-Suspension bonus swings immediately
    after. `has_combat_intent()` also fixed to recognize a decodable
    `CAST` tactic as combat intent -- [3.12]'s own quoted text already
    named "personal combat spells (including Charm)" alongside combat
    tactics, but the old check only looked at Melee/Fire Arrow, meaning
    a cast-only Encounter Plan would previously skip the King/Hero
    acceptance check entirely and never even reach real combat.
    `ChallengeExecutionResult` gains a new `fled: bool = False` field
    (a successful Charm, or Augur Combat cast first and shirking --
    distinct from an inconclusive draw), default `False` so every
    existing caller/test is unaffected.
  - **Augur Combat's own "cast later -> acts as Flee" branch is
    deliberately left unwired**, confirmed and documented rather than
    guessed: it needs a real Flee *tactic* and [5.6]'s own base-chance
    table, and neither exists anywhere in Challenge/Pursue today (unlike
    Search, which has both) -- `_resolve_personal_combat_cast()` returns
    `None` (no effect) for this one specific case, with the gap recorded
    in the module's own docstring rather than silently faked.
  - `turn/pursue_execution.py`: the armyless case now imports and reuses
    `resolve_challenge_combat()` directly (the same way it already
    reused `has_combat_intent`/`is_encounter_accepted`), replacing its
    own raw `resolve_encounter_combat()` call; `PursueExecutionResult`
    gains the same new `fled` field.
  - Non-breaking: full suite passed unchanged before any new tests were
    added (every new function is additive; the only existing-function
    change, `has_combat_intent()`'s widened CAST detection, doesn't
    affect any tactic list used by an existing test) -- 3223 passed.
  - 15 new tests across `test_challenge_execution.py` (2 for the
    `has_combat_intent()` CAST fix; Charm/Control-Undead-eligible-and-
    ineligible/Fireball/Words-of-Healing-heal-and-gate/Hand-of-Death/
    Mirror-Image/Gate-Demon/Psychic-Blast-bonus-attacks/both Augur-
    Combat branches) and `test_pursue_execution.py` (1, confirming the
    armyless case's own Charm-flee reuse) -- 3238 passed total.

- **Phase 291**: wires Personal-Combat spells into Duel
  ([7.1]), the third and last real Encounter consumer after Search
  (Phase 289) and Challenge/Pursue (Phase 290) -- `turn/battle_
  orchestrator.py _maybe_fight_duel()`'s own opt-in real-combat mode
  (`use_real_duel_combat=True`) previously only resolved Melee/Fire
  Arrow via `resolve_encounter_combat()`.
  - `turn/challenge_execution.py`: `_resolve_personal_combat_cast()`/
    `resolve_challenge_combat()` widened to accept `caster_leader`/
    `target_leader: LeaderState | None` -- a Duel side can be the
    provincial garrison commander ([7.1]: "has no abilities"), which has
    no real `LeaderState` at all (unlike Challenge/Pursue, where both
    sides are always real leaders). `caster_leader is None` makes any
    `CAST` tactic a silent no-op (no abilities to cast with);
    `target_leader is None` is read as an ordinary, alignment-unrecorded
    target -- every spell branch already treated an unset `alignment` as
    "not eligible/not immune," so this needed no new logic, only the
    `None`-guard on each `target_leader.alignment` access.
  - `turn/battle_orchestrator.py`: `_maybe_fight_duel()`/`fight_battle()`
    now import `resolve_challenge_combat()` (replacing `resolve_
    encounter_combat()`) and widen `duel_maneuvers` to accept either a
    bare `Maneuver` (Melee/Fire Arrow, Phase 273's own shape, still
    accepted unchanged) or a full `SearchTactic` (`CAST` with its own
    spell id) -- normalized to `SearchTactic` internally so both forms
    coexist in the same list. Each commander's own `LeaderState` (or
    `None` for the garrison-commander fallback) is looked up from
    `state.leaders` and threaded through to the spell dispatcher.
  - **A successful Charm (or Augur Combat cast first and shirking) is
    read as no duel occurring at all** (`loser_side=None`) -- [7.1]
    describes no "commander flees the duel" outcome, so this reuses the
    exact same fallback the function's own docstring already used for an
    astronomically-unlikely exhausted round cap. This falls out of the
    existing `combat_result.winner is None` check for free, since
    `resolve_challenge_combat()`'s own `ChallengeCombatOutcome` already
    sets `winner=None` on a `fled` outcome. Augur Combat's own "cast
    later -> acts as Flee" branch stays the same confirmed, unmodeled
    gap it already is for Challenge/Pursue (no Flee tactic/chance table
    exists for a Duel either).
  - Non-breaking: full suite passed unchanged before any new tests were
    added (the `None`-widening is backward-compatible for every real
    leader already in use, and normalizing a bare-`Maneuver`
    `duel_maneuvers` list is a no-op for the one existing test that
    passes one) -- 3238 passed.
  - 4 new tests in `test_battle_orchestrator.py`: a successful Charm
    reports no duel occurring and leaves both sides' strength untouched;
    a Fireball kill demoralizes the loser exactly like a Melee kill
    would; Control Undead against a garrison-commander (leaderless)
    target is correctly ruled ineligible with no roll consumed, falling
    through to Melee; and a defensive case confirms a CAST tactic from a
    hypothetical leaderless attacker Commander is a silent no-op rather
    than a crash -- 3242 passed total.

- **Phase 292**: the real round-based combat range engine, and
  spell disruption wired for real -- user-directed via `AskUserQuestion`
  ("Costruisci il motore round-per-round (Consigliato)"), after
  determining disruption could not be honestly wired at `turn/
  challenge_execution.py`'s previous atomic-tactic granularity (the same
  gap `turn/search_execution.py`'s own Phase 289 addendum had already
  flagged as this project's "largest single remaining piece of unbuilt
  personal-combat machinery").
  - **Corrected the shipped disruption formula.** The primary source
    (`RULES.AK` [5.1], confirmed identically in `ADDEND.AK`/`Regolamento
    AK.txt`) reads: "3 hit points will disrupt your spell 50% of the
    time, while a missed swing will disrupt you 30% of the time" -- this
    does **not** match this project's own Phase 179 "20% cumulative per
    hit, 95% cap" paraphrase, discovered once the real source text was
    located and read directly. Two distinct triggers, confirmed by the
    user via `AskUserQuestion` as: damage-scaled `50%/3 ≈ 16.67%` per
    damage point (`SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT`), and a flat
    30% (`SPELL_DISRUPTION_MISSED_ATTACK_CHANCE`) for a missed/dodged
    attack -- both capped at the same universal 95% this project already
    uses elsewhere. `turn/encounter.py`'s `spell_disruption_chance()`/
    `resolve_spell_disruption()` now take `damage_points` (was
    `hits_taken_this_round`); new `spell_disruption_chance_from_missed_
    attack()`/`resolve_spell_disruption_from_missed_attack()` model the
    second trigger. Words of Healing's own halved-rate wrappers were
    updated to match, plus new halved-rate missed-attack variants.
  - **`turn/encounter.py MeleeRoundOutcome`/`resolve_one_melee_round()`**:
    extracted from `resolve_melee_duel()`'s own internal per-round loop
    -- a thin, RNG-consumption-identical wrapper now calls it in a loop,
    verified zero behavior change. Exposes per-side per-round damage/
    miss detail (`damage_dealt_to_a`/`_to_b`, `a_attacked`/`b_attacked`)
    a round-based caller needs to feed disruption checks.
  - **`resolve_reactive_melee_swing()`**: a new one-directional Melee
    swing primitive -- the *target* (which has no Encounter Plan of its
    own, this project's established scoping) swings at a *casting*
    combatant, who doesn't swing back that round. Models [5.1]'s own
    "[melee attacks] will always have precedence" as the mechanism that
    makes disruption possible.
  - **`turn/challenge_execution.py resolve_challenge_combat()`**: now
    tracks a real `CombatRange` (starting `SPELL_RANGE`, per [5.0]'s own
    "Encounters usually begin at spell range"). `SHOOT` closes to
    `BOW_RANGE` first (one free, RNG-free round via the new `_close_to()`
    helper) then fires atomically via the unchanged `resolve_fire_arrow_
    duel()`; **at `MELEE_RANGE`, `SHOOT` is ignored outright** ("In the
    melee zone, only spells or hand-to-hand attacks"). `CAST` never needs
    to close range (spells are usable at every range); **at `MELEE_
    RANGE` specifically**, the target's reactive swing
    (`resolve_reactive_melee_swing()`) runs *before* the cast is even
    attempted -- a landed hit rolls the damage-scaled formula, a miss
    rolls the flat-30% one, and a disrupted cast never reaches `_resolve_
    personal_combat_cast()` at all ("the caster loses a turn" = the
    tactic consumed with no effect, the same outcome a failed cast-
    chance roll already produces). Disruption is deliberately **not**
    checked at `SPELL_RANGE`/`BOW_RANGE` (the target has no reciprocal
    Fire Arrow of its own modeled here -- an established, narrower scope
    boundary, not an oversight).
  - **`MELEE`'s own atomicity now depends on its position in the plan**:
    the *last* tactic (or the only one -- every real caller and pre-
    Phase-292 test's own shape) still fights the full atomic `resolve_
    melee_duel()` to its own conclusion in one call, unchanged. A `MELEE`
    tactic followed by more tactics -- the shape a plan needs to
    genuinely interleave "swing this round, cast next round" (the
    Marzials/Ablamor worked example's own "mutual Melee exchanges"
    interrupted by disrupted casts) -- now fights only **one round**
    (`resolve_one_melee_round()`) before falling through, letting a
    following `CAST` genuinely see `current_range is MELEE_RANGE`. An
    exhausted tactic list still defaults to Melee, forcing `current_
    range` to `MELEE_RANGE` and fighting the same atomic duel to its own
    conclusion, unchanged from before this phase.
  - **Out of scope, by explicit user direction**: `turn/search_
    execution.py`'s own richer tactic set (Steal/Talk/Fulfill/Scout/
    Use_MI/Beg, interleaved with Cast/Melee/Shoot) is a distinct future
    phase, not attempted here.
  - Non-breaking: full suite passed unchanged before any new tests were
    added at each step (the `resolve_one_melee_round()` extraction, then
    the range-engine rewrite) -- every real caller and test today only
    ever orders `MELEE` last, so the new one-round path is exercised only
    by genuinely new plan shapes -- 3242 -> 3248 -> 3254 passed across the
    three non-breaking checkpoints.
  - 6 new tests in `test_encounter.py` for `resolve_one_melee_round()`/
    `MeleeRoundOutcome` (no-death both-sides-damage, a recorded miss, a
    dead defender never swinging back, regeneration only when nobody
    died, and RNG-identical parity against the atomic `resolve_melee_
    duel()`), plus rewritten disruption-formula tests (`test_encounter.
    py`, 231 total in that file); 10 new tests in `test_challenge_
    execution.py` for the range engine itself (`_close_to()`'s own one-
    tier-at-a-time/never-widens behavior, last-vs-non-last `MELEE`
    atomicity, `SHOOT` ignored at melee range, both disruption triggers,
    a lethal reactive swing ending combat immediately, and `CAST` at
    `SPELL_RANGE` never checking disruption) -- 3264 passed total.

- **Phase 293**: extends the round-per-round engine to `turn/
  search_execution.py`'s own Search combat -- genuinely **bidirectional**
  this time, by explicit user direction (`AskUserQuestion`: "Bidirezionale
  completo (Consigliato)" over a narrower leader-only-parity option),
  since a Search guardian has a real Special Encounter Plan of its own
  (`models/monster_encounter_plan.py`), not just a passive target.
  - **The core bug this closes**: the guardian's own `CAST` entries were
    always burst-resolved as one upfront block, before Melee/Fire Arrow
    even began -- so a species like Dryad/Mermaid, whose real plan reads
    `MELEE, MELEE, MELEE, MELEE, MELEE, CAST(Charm), MELEE` (several real
    melee rounds before its own Charm), had that later Charm cast
    immediately alongside its opening tactics instead of several rounds
    into the fight. `_resolve_monster_casts()` now stops its own burst at
    the guardian's own *first* `MELEE` tactic (unchanged output for the
    overwhelming majority of species, whose plans only ever have one
    trailing `MELEE` anyway) instead of scanning past it for more `CAST`
    entries; everything from that point onward is walked one round at a
    time by the new `_resolve_melee_range_round()`, via a `monster_
    tactic_index` cursor shared with a new `_peek_monster_action()`/
    `_advance_monster_tactic()` pair.
  - **`_resolve_melee_range_round()`** generalizes `turn/challenge_
    execution.py`'s own Phase 292 disruption design to two real plans
    instead of one: each round, both the leader's own next tactic
    (`CAST`/`MELEE`) and the guardian's own peeked next tactic are
    resolved via the same four-way matrix -- Melee-vs-Melee (an ordinary
    mutual `resolve_one_melee_round()`), Melee-vs-Cast/Cast-vs-Melee
    (the melee side's own swing is the *other* side's reactive attack,
    `resolve_reactive_melee_swing()`, which can disrupt that cast via
    `resolve_spell_disruption()`/`resolve_spell_disruption_from_missed_
    attack()`), and Cast-vs-Cast (both attempt their own cast, no swings,
    no disruption check). `apply_temper_melee_setup()` is now called
    directly, exactly once per encounter, since the round-stepped path
    never goes through `resolve_melee_duel()`'s own internal call to it.
  - **A real bug found and fixed while building this**: a "Melee"
    response (either side) never advanced `monster_tactic_index` on its
    own -- only a resolved `CAST` did. For a guardian whose own plan
    repeats several `MELEE` entries before its next `CAST` (Dryad/
    Mermaid again), this meant the cursor could never progress past the
    first repeated `MELEE` entry at all, permanently blocking the later
    `CAST` from ever being reached. Fixed by advancing the cursor after
    *every* round the guardian answers with Melee, not just after a cast
    -- safe even on a genuinely final `MELEE` entry, since advancing past
    it and `_peek_monster_action()` reading "past the end" both already
    mean the same thing ("ME fino alla fine").
  - **Atomic fast path preserved for the common case**: a new `_monster_
    has_more_casts_pending()` lookahead (not just `_peek_monster_action()`'s
    own "what does it want to do *this* round" answer -- a guardian whose
    *immediate* next tactic is Melee can still have a real Cast waiting a
    few rounds later) gates both the `MELEE` tactic branch and the
    exhausted-tactic-list fallback: when neither side has any real casting
    left to do, the original atomic `resolve_melee_duel()` still runs
    (RNG/mock-identical to every pre-Phase-293 caller, the same proven
    parity Phase 292 already established) instead of looping the new
    primitives for no reason.
  - `MELEE`'s own last-vs-non-last split (Phase 292's own design) is
    reused unchanged for the leader's own plan; a trailing `Maneuver.
    SCOUT` doesn't count as "more tactics" for that check (Scout always
    resolves separately, after the whole walk, regardless of position).
  - **Out of scope, unchanged from Phase 292's own explicit scoping**:
    Search's own richer tactic set (Steal/Talk/Fulfill/Scout/Use_MI/Beg)
    stays exactly as it already was -- resolved inline at its own
    position in the leader's tactic walk, with no round-engine
    interaction (no guardian reaction, no disruption exposure). Only
    `CAST`/`MELEE`/`SHOOT` participate in the round engine, matching
    Phase 292's own scope on the Challenge/Pursue side.
  - Non-breaking: full suite passed unchanged before any new tests were
    added, through several intermediate fixes (the initial design broke
    55 tests by no longer calling the now-mocked `resolve_melee_duel()`
    at all; restoring the fast path, then correcting its own lookahead
    condition, then fixing the cursor-advance gap, each independently
    re-verified against the full suite) -- 3264 -> 3269 across the
    non-breaking checkpoints once the design stabilized.
  - 5 new tests in `test_search_execution.py`: the atomic fast path still
    fires when the guardian has nothing left to interleave; round-
    stepping engages when its own plan has a Cast beyond its first Melee
    (and that Cast is genuinely attempted, not skipped); the guardian's
    own Cast can be disrupted by either a landed swing (damage-scaled
    formula) or a missed one (flat 30%); and the leader's own Cast after
    a non-last Melee tactic can likewise be disrupted -- 3269 passed
    total.

- **Phase 294**: fixes a real Temper-setup gap in `turn/
  challenge_execution.py`'s own Phase 292 round engine, found while
  building the analogous (correct) version for Search (Phase 293).
  `apply_temper_melee_setup()` (Furia/Intimidazione/Slancio/Schivare,
  Phase 284) is normally applied exactly once, internally, by
  `resolve_melee_duel()` -- but `resolve_challenge_combat()`'s own
  non-last-`MELEE` round-stepping branch (a `MELEE` tactic followed by
  more tactics) never went through that function at all, so a caster's/
  target's own Temper effects silently never applied for that one plan
  shape. A new one-shot `melee_setup_done` flag now calls `apply_temper_
  melee_setup()` directly, exactly once, right before the *first*
  `resolve_one_melee_round()` call in that branch -- guarded so it never
  also fires when the atomic `resolve_melee_duel()` path is taken
  instead (which would double-apply Berserk's own bonus hit points and
  consume an extra roll). Every real caller/test only ever orders
  `MELEE` last, so the fix is inert for all of them -- it only changes
  behavior for the same genuinely new plan shape Phase 292's own
  docstring already flagged as the only thing exercising the one-round
  path at all.
  - Non-breaking: full suite passed unchanged before any new tests were
    added -- 3269 passed.
  - 2 new tests in `test_challenge_execution.py`: a Berserk caster's own
    bonus hit points now actually apply in the non-last-`MELEE` branch
    (isolated via a mocked `resolve_one_melee_round()`/`resolve_melee_
    duel()`, real seeded RNG only for the setup step itself); and the
    setup call fires exactly once even across two separate non-last
    `MELEE` tactics in the same plan -- 3271 passed total.

- **Phase 295**: wires the round-per-round combat engine into
  `turn/pursue_execution.py`, per explicit user request ("Facciamo il
  wiring anche in Pursue"). Investigation found the armyless case's own
  `execute_pursue()` already delegates its whole combat walk to `turn/
  challenge_execution.py resolve_challenge_combat()` -- established
  since the module's own "Phase 290 addendum", predating this project
  phase -- meaning it had *already* automatically inherited Phase 292's
  `CombatRange` round engine (spell-range Cast disruption, Bow-range
  Fire Arrow, non-last-`MELEE` one-round-at-a-time stepping) and Phase
  294's `apply_temper_melee_setup()` fix with zero further
  production-code changes needed for the core mechanic. Two things
  remained:
  - A stale docstring paragraph (the module's own "Fire Arrow (Phase
    273)" note) still claimed combat "walks `request.tactics` via
    `turn/encounter.py resolve_encounter_combat()`" -- true before
    Phase 290 but never updated when that addendum (further down the
    same docstring) switched the call to `resolve_challenge_combat()`.
    Corrected with a cross-reference to the Phase 290 addendum, plus a
    new Phase 295 addendum documenting the inheritance explicitly.
  - No test proved the inheritance was *real* (reachable through
    `execute_pursue()`'s own public API), as opposed to merely true by
    reading the source. Two new tests close that gap, mirroring the
    equivalent `test_challenge_execution.py` Phase 292/294 tests but
    driving them through `execute_pursue()` instead of calling
    `resolve_challenge_combat()` directly.
  - Non-breaking: full suite passed unchanged before any new tests were
    added -- 3271 passed.
  - 2 new tests in `test_pursue_execution.py`: a non-last `MELEE`
    tactic genuinely steps one round via `resolve_one_melee_round()`
    (not the atomic `resolve_melee_duel()`) when reached through
    `execute_pursue()`; and `apply_temper_melee_setup()` fires exactly
    once for a Berserk pursuer in that same branch -- 3273 passed
    total.

- **Phase 296**: fixes a real, previously-undetected bug found
  during a dedicated bug-hunt audit (three parallel reviews across the
  personal-combat engine, the mass-battle engine, and the turn-
  orchestration layer, each independently re-verified before acting on
  it) -- `roll_terrain_line_length_cap()` (rulebook [1.6]'s own Terrain
  Table line-length shortening, sourced since Phase 6) was fully
  implemented but never actually rolled by `battle_orchestrator.py
  fight_battle()`, the sole production caller of `resolve_battle()` --
  meaning the Phase 64 numeric-superiority outflanking bonus that
  depends on it (`RULES.AK` ~line 1362: "If a battle line is shorter
  than the terrain allows, the flanking second-line units of a force
  which is superior in numbers may outflank the enemy force... 100%
  strength instead of 50%") silently never applied in any real battle
  ever fought by this engine, regardless of terrain or force-size
  mismatch -- `terrain_line_length_cap` always defaulted to `None`.
  Fixed by rolling it once per battle, right before the `resolve_battle`
  call, against the province's own real terrain (`province.
  effective_terrain()`, already computed earlier in the same function).
  - **Two further confirmed bugs from the same audit, not yet fixed
    this phase** (deliberately scoped out -- see the audit's own
    findings for the full detail; each needs its own dedicated fix/test
    pass): (1) `apply_temper_melee_setup()` can be double-applied when a
    non-last `MELEE` tactic's own round-stepping falls through to the
    trailing atomic `resolve_melee_duel()` fallback in both `turn/
    challenge_execution.py` and `turn/search_execution.py`, compounding
    Temper bonuses; (2) `turn/aftermath.py`'s own Druidic insufficient-
    ability quality-improve-chance penalty (`led_by_insufficient_druid`,
    rulebook [7.5]) is never actually passed by any of `battle_
    orchestrator.py`'s 5 real `roll_quality_change()` call sites, even
    though the needed `druidic_shortfall` value is already computed and
    available there; (3) `turn_processor.py _apply_defend_battle_loss()`
    reads `dispatch_results[0]` unconditionally to detect a reinforced
    Defend leader's own battle loss, but a multi-attacker group's own
    dispatch list can have a validation-error entry (an illegal mover)
    at index 0 ahead of the real battle-bearing entry, silently skipping
    the loss-cancellation rule in that specific combination.
  - **A non-obvious side effect, not a regression**: `ScriptedRandom`
    (`tests/_helpers.py`) only overrides `.random()`/`.choice()`, not
    `.randint()` -- but CPython's own `random.Random.__init_subclass__`
    detects a subclass overriding `.random()` without also overriding
    `.getrandbits()`, and silently rebinds `randint()`/`randrange()`'s
    internal `_randbelow` to the `_randbelow_without_getrandbits()`
    implementation, which *does* consume from the scripted `.random()`
    queue (confirmed empirically, not assumed) -- meaning this fix's new
    `rng.randint()` call consumes one scripted float per real-terrain
    battle. Every existing `ScriptedRandom`-driven battle test needed
    exactly one extra leading/mid-sequence value added at the point
    `fight_battle()` now rolls the cap (right after any duel resolution,
    right before the 3 luck rolls) -- the same "update tests for new RNG
    consumption" precedent Phase 167 already established. Two `random.
    Random(seed)`-driven `turn_processor.py` tests needed a reselected
    seed (1 and 0, replacing 0 and 15) since the added draw shifted
    their own downstream deterministic outcome.
  - Non-breaking re-confirmed: after fixing every existing test's own
    RNG script for the new consumption, the full suite passed unchanged
    (3273) before any new test was added.
  - 2 new tests in `test_battle_orchestrator.py`: the roll is genuinely
    made against the province's own real terrain and forwarded to
    `resolve_battle()` (mocked-wiring check, not a fresh reimplementation
    of Phase 64's own `resolve_battle()`-level outflanking tests); and a
    true end-to-end proof, through a real (unmocked) `fight_battle()`
    call, that two identical attacker armies against a single defender
    on Plains now really does apply the 100%-instead-of-50% outflanking
    boost to the second-line unit -- 3275 passed total.

- **Phase 297**: fixes the second confirmed bug from the same
  bug-hunt audit that found Phase 296's terrain-line-length-cap gap --
  `apply_temper_melee_setup()` (Furia/Intimidazione/Slancio/Schivare,
  Phase 284) could be applied *twice* for a genuinely new Encounter Plan
  shape. Phase 294's own fix only guarded the *explicit*
  `apply_temper_melee_setup()` call made right before a non-last
  `MELEE` tactic's own round-stepping -- but `resolve_melee_duel()`
  itself always applies setup internally too, and every place `turn/
  challenge_execution.py`/`turn/search_execution.py` still call it
  atomically (the last-tactic path, the exhausted-tactic-list fallback,
  and, in `search_execution.py`, `_resolve_steal()`'s own caught-at-
  Melee-range branch) called it unconditionally. So a plan where an
  earlier non-last `MELEE` already ran real setup via round-stepping,
  then later reached one of those atomic paths (e.g. `[MELEE, TALK,
  MELEE]`, or a non-last `MELEE` followed by a caught `STEAL`), really
  did compound the effect -- confirmed live, not just read: a Cautious
  combatant's own defensive multiplier compounded 1.0 -> 0.9 -> 0.81
  instead of the intended single 0.9, and a Berserk combatant's own
  bonus hit points could apply twice.
  - **Fix**: `resolve_melee_duel()` (`turn/encounter.py`) gains a new
    `skip_temper_setup: bool = False` parameter -- default inert for
    every pre-Phase-297 caller, which never passes it at all. All five
    vulnerable call sites (two in `challenge_execution.py`, three in
    `search_execution.py`) now pass `skip_temper_setup=melee_setup_done`,
    which is `False` (no-op change) for every ordinary plan shape where
    the atomic path's own internal call is genuinely the first, and
    `True` only for the same narrow, genuinely-new plan shapes that
    triggered the bug.
  - Also corrects Phase 294's own docstring claim ("guarded so it never
    also runs when the atomic path is taken instead") in `turn/
    challenge_execution.py`, which was the false premise behind this
    bug going unnoticed.
  - Non-breaking: full suite passed unchanged (3275) before any new
    test was added.
  - 4 new tests: `test_encounter.py` unit-tests `skip_temper_setup`
    directly on `resolve_melee_duel()` (default still applies setup;
    `True` skips it); `test_challenge_execution.py` proves the fix live
    (unmocked `resolve_melee_duel()`, a Cautious caster's own
    `defensive_hit_multiplier` stays at 0.9, not 0.81, after a `[MELEE,
    TALK]` plan); `test_search_execution.py` proves the exhausted-
    fallback call site is correctly wired (`skip_temper_setup=True`
    reaches the mocked `resolve_melee_duel()` call) -- 3279 passed
    total.

- **Phase 298**: fixes the third confirmed bug from the same
  bug-hunt audit -- `turn/aftermath.py roll_quality_change()`'s own
  `led_by_insufficient_druid` parameter (rulebook [7.5]: "If it fought
  as a Green or Depleted unit because of insufficient Druidic ability,
  it has 60% and 20% (respectively) of the normal chance to improve")
  was fully implemented and unit-tested in isolation, but never actually
  passed by any of the 5 real `roll_quality_change()` call sites in
  `turn/battle_orchestrator.py` -- even though the exact value needed
  (`druidic_shortfall > 0`) is already computed per-army in `_build_
  battle_units()` for the strength-side penalty, right next to the
  already-wired, analogous `druidic_rear_targeting_blocked` flag.
  - **Fix**: `BattleUnit` (`turn/battle_line.py`) gains a new
    `led_by_insufficient_druid: bool = False` field, set the same way as
    `druidic_rear_targeting_blocked` but without that flag's own
    overflight-only gate (this penalty applies to any shortfall-led
    unit, not just overflight ones). `fight_battle()` builds one
    `army_id -> bool` lookup from `attacker_units`/`defender_units`
    right after `resolve_battle()` returns, and threads it into all 5
    call sites -- the 4 direct `roll_quality_change()` calls, plus
    `_retreat_or_disband()` (which gained the same parameter, forwarded
    to its own internal call; currently a no-op there since `turn/
    aftermath.py`'s own formula only consults the flag on the `is_
    winner=True` branch, kept for completeness/correctness if that
    scope is ever widened).
  - Non-breaking: full suite passed unchanged (3279) before any new
    test was added.
  - 2 new tests in `test_battle_orchestrator.py`: `_build_battle_units()`
    now sets `led_by_insufficient_druid=True` for the same foreign-race-
    led-army fixture the existing strength-side penalty test already
    uses; and a `fight_battle()`-level wiring proof (mocked `roll_
    quality_change()`) that a winning, Druid-shortfall-led army's own
    post-battle quality roll genuinely receives `led_by_insufficient_
    druid=True` -- 3280 passed total.

- **Phase 299**: fixes the fourth and last confirmed bug from
  the same bug-hunt audit -- `turn_processor.py _apply_defend_battle_
  loss()` (the rulebook [3.15] Defend-cancellation-on-loss check) read
  `dispatch_results[0]` unconditionally to find the battle a reinforced
  Defend leader had just been drawn into. That assumption breaks for
  `_dispatch_multi_attacker_lmove()`'s own dispatch lists: an illegal
  mover (e.g. moving out of a province contested by their own kingdom)
  gets its validation-error `PhaseDispatchResult` appended *before* the
  real `MultiAttackerMoveResult` entries for the movers who actually
  joined the battle, so a multi-attacker group with at least one invalid
  mover declared first could have its own real battle result sitting at
  index 1 or later -- reading only index `[0]` then silently found no
  battle at all (an error entry carries none) and never cancelled the
  Defend order despite a genuine loss.
  - **Fix**: `_apply_defend_battle_loss()` now scans every entry in
    `dispatch_results` via `_extract_battle_winner()` and takes the
    first non-`None` winner found, instead of trusting index `[0]` --
    at most one battle is ever produced for a single `target`, so the
    first real winner found is unambiguously the right one.
  - Non-breaking: full suite passed unchanged (3280) before any new
    test was added.
  - 1 new test in `test_turn_processor.py`:
    `test_run_turn_defend_battle_loss_blocks_a_later_redeclaration_with_a_leading_group_error`
    combines the illegal-mover-in-a-multi-attacker-group pattern (see
    `test_run_turn_excludes_an_illegal_contested_mover_but_still_groups_
    the_rest`) with the Defend-reinforcement-and-loss pattern (see
    `_defend_loss_state()`): an illegal mover is declared first so its
    error lands at group index 0, two real attackers behind it win the
    battle against a reinforced Defend leader, and the Defend order is
    still correctly cancelled -- verified to genuinely catch the bug by
    temporarily reverting the fix and confirming this exact test then
    fails -- 3281 passed total.

- **Phase 300**: fixes the first confirmed bug from a second
  bug-hunt audit round (three fresh parallel reviews across economy/
  army-management execution, spell casting/world-content generation,
  and kingdom/succession/intelligence/reporting -- the last of these
  found nothing convincing after a genuine trace-through, reported
  plainly rather than padded with speculative nitpicks) --
  `apply_plague_exposure()` (`turn/cast_execution.py`, shared by
  `_execute_plague()` and `turn/plague_spread.py`) only ever checked
  an exposed army's *own* kingdom for `Discovery.PENICILLIN`. The
  sourced Discovery text (`models/discovery.py`) has a second clause
  this only implemented half of: "Your armies are protected wherever
  they go, **and all armies (yours and your ally's) are protected in
  your provinces**." An allied army with no Penicillin of its own,
  garrisoned inside a Penicillin-owning kingdom's own territory, could
  be outright destroyed by the ordinary Plague roll instead of only
  ever facing the documented flat 50% quality-downgrade risk.
  - **Fix**: `apply_plague_exposure()` now also looks up `coord`'s own
    province-owner kingdom; an exposed army is protected (the flat
    downgrade-only branch) if either its own kingdom owns Penicillin
    (unchanged) or the province owner does and is allied with (or the
    same as) the army's kingdom (`GameState.is_allied()`, which already
    treats same-kingdom as allied, covers both halves of the clause
    with one check).
  - Non-breaking: full suite passed unchanged (3281) before any new
    test was added.
  - 2 new tests in `test_cast_execution.py`: an allied, Penicillin-less
    army standing in a Penicillin-owning kingdom's own province now
    gets the flat-downgrade protection instead of being destroyed; a
    *non*-allied army in that same province gets no protection at all,
    confirming the fix is alliance-gated, not blanket -- 3283 passed
    total.

- **Phase 301**: fixes the second confirmed bug from the
  same second bug-hunt audit round -- `turn/search_execution.py
  _resolve_fulfill()` credited `MeritTally.monster_hp_neutralized` with
  `monster_starting_hit_points // 2` (a negotiated Fulfill's own half-
  credit, rulebook page 51's "metà dei punti se neutralizzato con
  trattative"), but `turn/merit_points.py defender_merit_points()`
  halves that same field *again* when computing the Defender office's
  score -- both `MeritTally.monster_hp_neutralized`'s own field comment
  (`models/game_state.py`) and `merit_points.py`'s own module docstring
  already documented the field as a raw, unhalved count with the
  halving applied exactly once, by the formula function. The double
  halving quartered a negotiated monster's real credit instead of
  halving it. Hid because each half of this two-function pipeline had
  its own isolated test -- neither exercised both together.
  - **Fix**: `_resolve_fulfill()` now credits the raw
    `monster_starting_hit_points`, matching the field's own documented
    contract; `defender_merit_points()`'s own halving is unchanged and
    is now the pipeline's only halving.
  - Non-breaking except the one existing test that (correctly, per the
    bug's own signature) asserted the old, wrong pre-halved write --
    updated in place to assert the raw value instead; full suite
    otherwise passed unchanged (3283) before any new test was added.
  - 1 new end-to-end test in `test_search_execution.py`:
    drives a real `execute_search()` Fulfill-honored call and then
    calls `defender_merit_points()` on the resulting tally in the same
    test, asserting the final credited score is exactly half the
    monster's starting HP -- closing the exact "each half tested in
    isolation" gap that hid the bug -- 3284 passed total.

- **Phase 302**: fixes the third and last confirmed bug from
  the second bug-hunt audit round -- `Discovery.ANALYTICAL_PSYCHOLOGY`
  (a Kingdom-level ward against enemy Charm casts, sourced text quoted
  in full in `models/discovery.py`) was declared as `Spell.CHARM`'s
  entry in `DISCOVERY_ANTISPELL_TARGET` but never consulted anywhere in
  `turn/cast_execution.py _execute_charm()` -- unlike its 15 sibling
  anti-spell Discoveries (each either wired or explicitly documented as
  deferred, per Phase 270's own accounting), this one was silently
  inert despite Charm's own base mechanic already being a real, working
  consumer with nothing else blocking it. Unlike the other two bugs
  this round, the source text is explicit that Analytical Psychology
  does *not* block Charm outright: "the spell will work, but it wears
  off at the end of the turn, and the charmed character will never
  Search features or risk combat" -- a genuinely different shape of fix
  from a simple guard clause, since this project had no "revert a
  mutated value at end of turn" mechanism anywhere yet (every existing
  "persistent for the rest of the turn" field is a caller-clears-it
  boolean flag with no prior value to restore).
  - **Fix**: `LeaderState` gains
    `analytical_psychology_revert_kingdom_id: int | None = None`.
    `_execute_charm()` still reassigns `kingdom_id` exactly as before,
    but if the target's own (pre-charm) kingdom owns the Discovery, also
    records their original `kingdom_id` into the new field. `turn/
    turn_processor.py run_turn()` gains a new
    `_revert_analytical_psychology_charms()` sweep, called once after
    every phase has dispatched, that restores `kingdom_id` for any
    leader with the field set and clears it -- the first genuine
    end-of-turn revert consumer this project's turn loop has needed.
    "Never Search" is enforced directly: `turn/search_execution.py
    execute_search()` now refuses immediately (before any real
    encounter resolution) while the field is set. "Risk combat" needed
    no separate enforcement, since Search is the only combat-risking
    action this project's own Charm precondition (a co-located,
    army-less target) leaves reachable for a newly-charmed character.
  - Non-breaking: full suite passed unchanged (3284) before any new
    test was added.
  - 5 new tests: `test_cast_execution.py` proves a protected target's
    Charm still succeeds (matching an unprotected target) while
    correctly queuing the revert, and that an unprotected target never
    sets the new field at all; `test_search_execution.py` proves
    `execute_search()` refuses outright for a leader with the field
    set; `test_turn_processor.py` proves the fix through two real,
    unmocked end-to-end `run_turn()` calls -- a protected Charm is back
    under its own original kingdom by the time `run_turn()` returns
    (verified to genuinely catch the bug by temporarily disabling the
    new sweep and confirming this exact test then fails), while an
    ordinary unprotected Charm is left charmed, exactly as before --
    3289 passed total.

This completes the second bug-hunt audit round's own three confirmed
findings (Phases 300-302), alongside the first round's four (Phases
296-299) -- seven real, previously-undetected bugs found and fixed
across two dedicated audit passes this project has run so far.

- **Phase 303**: closes Recruit's own long-flagged "never
  blocks recruiting in a non-owned, non-allied province" gap (see
  Phase 261's/262's own notes above), sourced from RULES.AK [3.4],
  quoted in full: "You can Recruit armies from the populace only if
  you own the province, but mercenaries can be Recruited in any
  province by any character, even a King who owns no provinces." This
  project only ever enforced the second half -- a levy (no matching
  mercenary present) used to succeed in any province at all, including
  one owned by a hostile kingdom or unclaimed/non-player territory.
  - **Fix**: `RecruitExecutionResult` gains a new `territory_blocked:
    list[ArmyType]` field. `execute_recruit()` now checks for a
    hireable co-located mercenary *before* deciding whether the
    request can proceed -- `can_levy = province.owner_kingdom_id ==
    kingdom_id or in_ally_territory` (ally territory is already gated
    by the existing Treat-permission check, Phase 261) gates only the
    populace-levy path; a genuine mercenary hire still proceeds in any
    province, unconditionally, exactly as the quoted sentence's own
    second half requires. No treasury debit happens for a
    territory-blocked type. The paragraph's later "You can never
    Recruit armies belonging to another kingdom" needed no separate
    fix -- `GameState.mercenaries_at()` already only returns
    `kingdom_id is None` armies, so a kingdom-owned army was never
    mistakenly hireable as a mercenary to begin with.
  - Non-breaking: full suite passed unchanged (3289) before any new
    test was added.
  - 3 new tests in `test_recruit_execution.py`: a levy in a
    hostile (unallied-owned) province is blocked and the treasury
    stays untouched; a levy in an unclaimed (`owner_kingdom_id=None`)
    province is likewise blocked; a co-located mercenary in that same
    hostile province is still hireable, proving the territory gate
    never touches the mercenary path -- 3292 passed total.

- **Phase 304**: closes Tactical Practice's own long-flagged
  "multi-leader army pooling" gap (Phase 167's/263's own notes above),
  sourced from RULES.AK [6.1], quoted in full: "If two leaders Practice
  Tactics together, their armies are pooled into the same training
  maneuvers." Worse than merely missing: `turn/turn_processor.py
  run_turn()`'s own Phase 46 same-ability/same-location grouping rule
  doesn't distinguish Tactical from any other ability, so two co-located
  leaders who both ordered Practice Tactical the same phase were already
  being grouped and routed to `execute_practice_group()` -- which
  unconditionally refused Tactical (`not_implemented_for_ability=True`
  for the whole group), silently training *nobody at all*, while the
  (bypassed) single-leader path was the only one that ever actually
  rolled. A multi-leader Tactical Practice order was strictly worse than
  a solo one, not just narrower.
  - **Fix**: new `turn/practice_execution.py
    execute_practice_tactical_group()` pools every army commanded by any
    of the co-practicing leaders into one shared training-and-inspiration
    pool before the per-army roll -- an army is eligible if *any* pooled
    army (regardless of which co-practicer commands it) sits at a
    strictly higher *original* Quality tier, then rolls independently at
    its own tier's `TACTICAL_TRAINING_CHANCE`, exactly as the solo case.
    `execute_practice_group()` now special-cases `Ability.TACTICAL` to
    call it instead of refusing the whole group. Each co-practicer's own
    `PracticeExecutionResult.trained_army_ids` still reports only their
    own armies that trained, matching the solo case's own reporting
    shape -- no caller ever sees another leader's army id mixed into
    their own result.
  - One pre-existing test
    (`test_execute_practice_group_tactical_is_not_implemented_for_the_whole_group`)
    asserted the old, buggy "trains nobody" behavior -- renamed and
    updated in place to assert the fix instead, the same "expected, not
    a regression" pattern already established for prior phases' own test
    updates. Non-breaking otherwise: full suite passed unchanged (3296)
    before any further new test was added.
  - 5 new tests: `test_practice_execution.py` proves a pooled army trains
    off another co-practicer's inspiring army that its *own* leader's
    command alone could never provide, proves the solo mechanic
    genuinely can't do this (same setup, `execute_practice_tactical()`
    directly), proves each leader's own result only ever lists their own
    army ids even when both co-practicers' armies train in the same
    call, and proves the `len(leader_ids) < 2` guard still applies to
    the new Tactical path; `test_turn_processor.py` proves the fix
    end-to-end through a real, unmocked `run_turn()` call with two
    co-located Tactical practicers -- 3297 passed total.

This closes both halves of the user's "sviluppiamo il gioco" request
this session: Recruit's territory gate (Phase 303) and Tactical
Practice's army pooling (Phase 304), the two concrete, verified-open
feature gaps identified from the README's own "Not yet implemented"
section.

- **Phase 305**: closes the character-vs-character half of
  Steal [ST] (rulebook [5.5]) -- `turn/search_execution.py`'s own
  `_resolve_steal()` only ever handled Search's guardian-monster target;
  `turn/challenge_execution.py`'s own docstring flagged the general case
  directly ("Steal isn't checked here (a separate, still-unmodeled
  tactic)"). Found via a background research agent's own systematic
  read-through of the Italian `Regolamento AK.txt` rulebook against this
  project's implementation, cross-checked against source before being
  presented as a real gap.
  - [5.5] quoted in full: "Il personaggio tenta di rubare il suo
    avversario, Re, Eroe o mostro che sia... Se la tattica Steal riesce
    il personaggio può portar via oro o uno o più oggetti magici (sempre
    che siano presenti). La probabilità base di riuscita è del 15% più
    15% per livello di abilità... Se il ladro prende di mira un
    personaggio che è alla guida di un esercito le sue probabilità di
    riuscita sono dimezzate... Se il ladro fallisce... le probabilità di
    evitare la cattura sono in funzione del livello di abilità del
    ladro. In caso di cattura le possibilità sono tre: se il ladro è un
    Eroe che ha provato a derubare un Re o un altro Eroe che comanda
    unità militari, viene giustiziato; se il ladro è un personaggio che
    ha tentato di derubare un mostro o un Eroe che non comanda unità
    militari, si ha un combattimento individuale, a una distanza scelta
    a caso; se il ladro è un Re che ha tentato di derubare un altro Re,
    perde metà dell'oro della sua tesoreria come prezzo del riscatto (se
    non ha oro verrà giustiziato)."
  - **Reuses, doesn't reinvent**: `turn/encounter.py`'s own
    `steal_success_chance()`/`resolve_steal_attempt()`/
    `resolve_steal_evasion()` (Phase 239) already implement the base
    success formula, the target-leads-an-army halving, and the
    post-failure evasion roll with no leader-vs-monster assumption baked
    in -- reused unchanged.
  - **New in `turn/challenge_execution.py`**: `_apply_successful_theft()`
    transfers one held item (the victim's first, if any) via the
    existing `GameState.transfer_item()` registry (Phase 140) --
    "how many" read as one, matching `execute_give()`'s own one-item-
    per-order convention. Gold theft's own magnitude stays unmodeled
    (confirmed absent in both sources, the same "confirmed absent" note
    `turn/encounter.py`'s own Phase 239 addendum already gave for the
    King-victim case). `_resolve_steal_tactic()` implements all three
    sourced capture consequences off `LeaderState.is_king` and whether
    the target commands an army: Hero-thief-vs-(King-or-army-Hero) is
    executed; King-vs-King pays half the thief's own kingdom treasury as
    ransom (or is executed if that treasury is already empty); anyone
    caught targeting a monster or non-army Hero fights a personal-combat
    encounter at a freshly-rolled random range. One combination the text
    doesn't cover -- a King caught robbing a non-King army-commanding
    Hero -- is left genuinely unresolved rather than guessed at.
  - `resolve_challenge_combat()`'s own tactic walk gains a `Maneuver.
    STEAL` branch dispatching to the above, automatically extending to
    `turn/pursue_execution.py` (which already reuses this same function)
    with no changes needed there. `has_combat_intent()` is unchanged --
    Steal still isn't itself "combat intent" per [3.12]'s own text.
    Search's own narrower monster-target `_resolve_steal()` is untouched.
  - Not addressed: [3.12]'s own English-only "chance is halved when
    Steal is used in a restricted encounter" clause describes a second,
    textually distinct halving condition from the Italian target-leads-
    an-army halving already wired -- flagged in `challenge_execution.py`'s
    own docstring as confirmed-but-unresolved rather than guessed at.
  - 17 new tests in `test_challenge_execution.py`: item theft transfers
    exactly one item and is a no-op when the victim holds nothing; the
    success/evasion/capture branches of `_resolve_steal_tactic()`
    (execution for a Hero robbing a King or an army-commanding Hero,
    King-vs-King ransom and its no-gold-execution edge case, combat for
    both thief types against a non-army Hero, the unresolved King-vs-
    army-Hero combination, and the no-LeaderState no-op consuming no
    RNG); and `resolve_challenge_combat()`'s own STEAL wiring across all
    three capture-combat ranges plus the success/executed fall-through
    cases -- 3314 passed total.

- **Phase 306**: wires Steal's own narrative text into the
  report layer, plus a correctness fix to Phase 305 found in the course
  of that research -- requested directly ("crea un testo nel report"),
  building on Phase 305's own newly-implemented mechanic.
  - **Two real, previously-unconsumed renderers were already sitting in
    `report/turn_report.py`, sourced and tested since Phase 105/119,
    just never dispatched by any caller**: `render_sneak_detected()`
    (`SNEAKUP.X`, a failed Steal maneuver caught mid-theft, ending with
    a range clause) and `render_steal_caught_and_ransomed()` (`_LRans`,
    the exact King-vs-King ransom narrative Phase 305's own `"ransom"`
    branch implements). New `describe_steal()` composer dispatches to
    them off `steal_outcome`/`steal_capture_range`; the other four
    outcomes (`success`/`evaded`/`executed`/`unresolved`) have no
    sourced template and render nothing, the same "no source, no guess"
    convention every other `describe_*` composer already follows.
  - **A real bug found while researching how to expose the "combat"
    range for narration**: [11.3]'s own worked example ("CA-IN, ST, FL,
    ME" -- cast Invisibility, attempt Steal, if caught try to Flee, if
    that fails Melee) proves getting caught should hand control to the
    plan's *own next tactic*, not atomically resolve a duel the way
    Phase 305 originally built it (mirroring Search's own precedent,
    which turned out not to generalize here). Fixed: the STEAL branch
    now sets `current_range` outright to the freshly-rolled range and
    lets the tactic walk continue, the same way SHOOT/MELEE already
    leave `current_range` for whatever follows -- a following `MELEE`
    (as in the worked example) picks up correctly; `FLEE` stays
    unwired (a separate, already-documented gap); an exhausted list
    still falls through to the pre-existing "defaults to Melee" tail.
  - `ChallengeCombatOutcome`/`ChallengeExecutionResult` (and
    `PursueExecutionResult`, which shares the same combat core) gain
    `steal_outcome`/`steal_capture_range` fields, threaded through every
    return site in `resolve_challenge_combat()` -- not just a terminal
    STEAL branch -- so the report layer can narrate the Steal sub-event
    even when a later tactic decides the encounter's actual winner.
  - Also newly documented (no code change): a Steal-only plan (no
    Melee/Fire-Arrow/decodable-Cast alongside it) never reaches
    `resolve_challenge_combat()` at all, since [3.12] deliberately
    excludes Steal from "combat intent" and `execute_challenge()`
    short-circuits before that. Both real worked examples always pair
    `ST` with a real combat tactic, so this is left as a documented,
    unattested-shape gap rather than fixed speculatively.
  - 5 new tests in `test_turn_report.py` covering `describe_steal()`'s
    ransom/combat/no-template/defensive-no-range branches and its reuse
    for `PursueExecutionResult`; 2 pre-existing Phase 305 tests in
    `test_challenge_execution.py` rewritten (the old atomic-duel
    assumption no longer holds) plus 1 new test proving the worked
    -example flow end-to-end -- 3319 passed total.

- **Phase 307**: replaces `turn/multiple_contingents.py`'s own
  invented `SAME_ORIGIN_UNITE_CHANCE`/`DIFFERENT_ORIGIN_UNITE_CHANCE`
  constants (85%/30% flat) with the real MARCH TABLE -- requested
  directly, after the earlier rulebook-comparison research flagged this
  as a genuine, verified gap: a precise table exists in both available
  sources (`RULES.AK [4.12] MARCH TABLE`, English, and Regolamento
  AK.txt's own "TABELLA DELLA MARCIA", Italian -- word-for-word the same
  figures), keyed by March ability level (0-4) x distance between the
  two forces' origin provinces (0/1/2+), ranging 20%-100%.
  - New `MARCH_UNITE_CHANCE`/`march_unite_chance()` in
    `multiple_contingents.py` implement the table's own "Contingents
    Unify %" half (the "Extra moves for..." half is a separate,
    still-unmodeled land-movement-range bonus, out of scope here).
    Distances beyond 2 and levels beyond 4 clamp to the table's own
    last known value rather than extrapolating.
  - **A design call the source itself doesn't disambiguate, documented
    rather than guessed**: [4.12]'s own prose ("the character with
    Forced March ability has a *better* chance of uniting") describes
    one character's own advantage, not a combined figure -- read here as
    each attacker's own March level driving their own chance of joining
    an already-forming group (`roll_unite_for_battle(a, b, rng)` uses
    `a`'s own level, `a` always being the one being asked "does this one
    manage to unite", per `group_attackers_into_battles()`'s own call
    site), not the founding member's level. "Distance to 2nd force" is
    the real `hex_distance()` between the two origins, not a guessed
    proxy. Naval's own analogous bonus ([4.13], "in a manner similar to
    March ability") has no numeric table of its own in either source --
    left unmodeled, the same "confirmed mechanic, no sourced magnitude"
    treatment as everywhere else in this project. Eagles/Dragons' own
    "not affected by March ability" carve-out also isn't modeled --
    `Attacker` has no army-composition field to check it against.
  - `Attacker` gains a `march_level: int = 0` field;
    `battle_orchestrator.py fight_multi_attacker_battle()` now looks up
    each party's own real March skill (`effective_skill_level(state,
    ..., Ability.MARCH)`) instead of leaving every attacker at the
    table's own floor.
  - Two pre-existing `test_turn_processor.py` tests (real, unscripted
    `random.Random(0)` sequences) flipped from uniting to not-uniting
    once the flat 85% became the level-0 table's own 80% -- fixed by
    giving those tests' leaders a real March-4 skill (guaranteeing
    100% union at same-origin), the same "expected, not a regression"
    test-update pattern this project has used throughout.
  - 4 new tests (`test_multiple_contingents.py`: the table matches the
    sourced figures exactly, clamping at both ends, the joining
    attacker's own level driving the outcome; `test_battle_orchestrator
    .py`: `fight_multi_attacker_battle()` reads a real leader's own
    March-4 skill from `state.leaders`, not a hardcoded default) --
    3323 passed total.

- **Phase 308**: replaces `turn/merit_points.py`'s flat
  +1-per-unit/-1-per-unit Gran Maresciallo (Marshal) and Grande
  Ammiraglio (Admiral) battle scoring with `Regolamento AK.txt`'s own
  "NUOVE REGOLE E MODIFICHE" quality table -- requested directly, after
  the same rulebook-comparison research that produced Phase 307 flagged
  this as a second genuine, verified gap. Quoted in full: "Adesso per la
  Carica di Maresciallo conta la qualità delle unità sconfitte secondo
  questa tabella: Reclute 0 punti / Medio 1 punto / Veterani 2 punti /
  Crack 3 punti / Elite 4 punti. Una Garrison che attacca ha un
  modificatore di -1 su questa tabella (una Garrison Crack che attacca e
  viene distrutta dà solo 2 punti al generale che l'ha vinta)."
  - New `MARSHAL_QUALITY_POINTS`/`battle_quality_points()` in
    `merit_points.py` implement the table plus the Garrison-attacker
    modifier. `Quality.DEPLETED` (unlisted in the source table) clamps
    to 0, the same "clamp rather than extrapolate" convention Phase
    307's `march_unite_chance()` established. The Garrison modifier's
    own per-unit floor is left unstated by the source (its worked
    example only tests the still-positive Crack case), so the
    subtraction is applied literally with no invented floor -- a
    defeated Green attacking Garrison scores -1, not 0.
  - **Extended to Admiral too, reasoned explicitly rather than
    guessed**: the quoted text names only "la Carica di Maresciallo",
    but this project's own pre-existing docstring already treats
    Admiral's battle term as "the same won/lost-unit formula as
    Marshal... for naval battles" (one shared formula per the original
    page-51 table), and the user's own request named both offices
    together.
  - `MeritTally`'s battle counters renamed (`models/game_state.py`):
    `land_battles_won_enemy_units`/`land_battles_lost_own_units`/
    `naval_battles_won_enemy_units`/`naval_battles_lost_own_units` ->
    `..._won_points`/`..._lost_points`, since they now hold
    quality-weighted points, not raw unit counts.
    `turn/battle_orchestrator.py _record_battle_merit()`'s signature
    changed from two unit-count integers to the real `attacker_armies`/
    `defender_armies` lists, so it can sum `battle_quality_points()`
    over the losing side's real `ArmyState.army_type`/`.quality`
    instead of a flat per-unit constant.
  - 9 pre-existing tests updated for the rename/signature change (6 in
    `test_battle_orchestrator.py` now build real `ArmyState` lists
    instead of passing unit counts; 1 in `test_game_state.py` and 2 in
    `test_merit_points.py` are simple field renames) plus 6 new tests
    (`test_battle_quality_points_*`/`test_marshal_quality_points_table_
    matches_the_rulebook` in `test_merit_points.py`, and a dedicated
    `test_record_battle_merit_applies_the_attacking_garrison_modifier`
    in `test_battle_orchestrator.py` reproducing the rulebook's own
    Crack-Garrison worked example) -- 3329 passed total.

- **Phase 309**: enforces Skeletal Army's own 350-unit world
  cap and ~10%/turn graveyard decomposition -- `Regolamento AK.txt`
  [4.2.5] (quoted in full): "Il numero totale di unità militari
  consentito nel gioco (sia viventi che morte) è di 350, perciò dopo le
  prime fasi, a ogni turno un 10% circa delle unità distrutte in
  precedenza è destinato alla decomposizione. Quando si supera il
  limite di 350, le unità distrutte da più lungo tempo si decompongono
  automaticamente." `turn/cast_execution.py _execute_skeletal_army()`'s
  own docstring had explicitly flagged this half of the rule as
  unenforced since Phase 60.
  - New `turn/skeletal_decay.py`: `WORLD_UNIT_CAP = 350`,
    `GRAVEYARD_DECAY_FRACTION = 0.10`, `decompose_graveyard()`. Gate:
    only once `len(state.armies) + total graveyard entries` exceeds 350
    (the more literal of the rulebook's own two sentences). Rate:
    `round(graveyard_size * 0.10)` -- the same "`round()` for an
    approximate rulebook percentage" precedent `turn/spy_table.py`
    already established; no invented minimum-of-1 floor, so a small
    graveyard can round to 0 removed even while over cap. Priority:
    oldest-destroyed first.
  - **User-clarified scope, not guessed**: only `battle_graveyard`
    entries (destroyed armies, not yet raised) ever decompose -- an
    already-risen Skeletal Army (a real, live `ArmyState` with
    `is_skeletal=True`) never decomposes via this mechanic, commanded
    or not, since it's alive, not a graveyard entry. `decompose_
    graveyard()` never touches `state.armies`.
  - `GraveyardEntry.death_seq` (new field, defaults to 0) and
    `GameState.graveyard_death_counter` close the "entries aren't
    turn-stamped" gap `GraveyardEntry`'s own Phase 60 note flagged --
    a monotonic insertion-order counter, not a real turn number, just
    precise enough to answer "which died longest ago."
    `record_battle_death()` now stamps it.
  - Wired once per game turn, at the same end-of-`run_turn()` point
    `turn/turn_processor.py`'s own Gate Angel visit and Analytical
    Psychology revert already run -- the one unambiguous "once per
    turn" boundary this phase-by-phase loop offers.
  - 8 new tests: `test_skeletal_decay.py` (7 -- under-cap no-op,
    oldest-first removal, cross-province global ordering, an emptied
    province key getting deleted, rounding down to 0 for a small
    graveyard, live armies including a commanded Skeletal Army staying
    untouched, `record_battle_death()`'s monotonic `death_seq`) plus 1
    `test_turn_processor.py` wiring test proving `run_turn()` itself
    triggers the decay -- 3337 passed total.

- **Phase 310**: closes four Kill_Enemy ([4.25.2]) gaps
  flagged directly by the user -- the coma variant, the Berserk
  counterattack on a failed cast, King immunity, and the Special-Place/
  army-leading-Hero halving. `Regolamento AK.txt` quoted in full: "Se
  fallisce, la vittima designata attaccherà l'autore dell'incantesimo
  assumendo per l'occasione un temperamento Berserk... Se viene
  utilizzato come incantesimo d'Azione può succedere che, invece di
  morire, la vittima cada in coma profondo... tutti i suoi Talenti sono
  ridotti a livello zero, ma possono essere ripristinati con un
  incantesimo di Resurrezione... la possibilità di riuscita è ridotta
  alla metà in un incontro in un Luogo Speciale o contro un Eroe che
  comanda unità militari... I Re sono immuni a questo incantesimo."
  - **King immunity** and the **halving** (either a Special Place
    feature at the shared province, or the target leading an army) are
    both checked in `_execute_kill_enemy()`; the halving is passed into
    `_roll_cast_success()`'s new `success_chance_multiplier` param
    (default 1.0, every pre-Phase-310 caller unaffected), applied
    before the 95% cap at the same point the Pagan bonus already is.
    The rulebook's other named halving trigger -- casting at a monster
    guarding a Special Place -- is documented as structurally
    unreachable here: this project's Kill_Enemy only ever targets a
    `LeaderState` (never a Monster), the same "Action-cast only, no
    Individual-Combat dispatch path" gap the coma reasoning below also
    rests on.
  - **Coma**: since this project's Kill_Enemy is *only* ever cast as an
    Action spell, a success now always sets `LeaderState.is_comatose =
    True` instead of removing the leader -- no percentage for "può
    succedere" is sourced anywhere (English `RULES.AK` omits the coma
    variant entirely), so this reads the Action-cast success as always
    producing it, a documented judgment call. `is_comatose` (new field)
    makes `turn/discovery_effects.py effective_skill_level()` read 0
    unconditionally for that leader -- one choke point covering every
    real consumer (Cast rolls, Tactical/Naval combat bonus, Duel
    selection, Merit Points, ...) -- without ever mutating the real
    `skills`, so nothing needs restoring on cure.
    `turn/practice_execution.py` additionally gates Practice itself
    outright for a comatose leader (the one consumer that reads
    `skills` directly, bypassing `effective_skill_level()`) --
    `Ability.TACTICAL` stays unaffected, since training the leader's
    own armies doesn't depend on the leader's own ability. The
    comatose leader is never removed from `state.leaders` and no
    action is blocked -- per the user's own clarification, "potrà
    comunque fare tutte le azioni... come se fosse su un letto,
    trasportato dai suoi scudieri."
  - **Berserk counterattack**: on a failed cast, a real, immediate
    `resolve_melee_duel()` between the target (temper forced to
    `Temper.BERSERK` "for the occasion" -- their own recorded
    `LeaderState.temper` is untouched) and the caster (their own real
    temper) -- "quella stessa fase" read as resolving inline, not
    deferred. Whoever loses is removed via `state.remove_leader()`,
    the same convention `turn/challenge_execution.py` already
    established for personal-combat winners/losers.
    `CastExecutionResult.kill_enemy_berserk_winner` (new field) records
    which side won, for a caller that wants to narrate it.
  - **Resurrection cures a coma too** ([4.25.2]: "possono essere
    ripristinati con un incantesimo di Resurrezione"), a new branch in
    `_execute_resurrection()` checked before the Royal-Heir case: a
    living, `is_comatose` target clears the flag on success and --
    the one deliberate divergence from an ordinary dead-Hero revival,
    per the user's own 2026-07-31 clarification -- never changes
    `kingdom_id`, even cast by a hero/King of another kingdom. No
    skill-restoration logic exists because the real values were never
    touched.
  - 9 pre-existing tests updated -- already-passing tests whose
    Kill_Enemy examples now exercise the new Berserk/coma paths: 2 rewritten to assert
    `is_comatose` instead of removal, 2 switched from Kill_Enemy to
    Charm (their own 95%-cap/Pagan-bonus generic tests would otherwise
    trip the new Berserk RNG consumption), 2 in `test_use_mi_execution.py`
    updated for the wand-cast coma outcome, 1 given an explicit
    `is_comatose is False` assertion (Hidden Tattoos).
  - 13 new tests: `test_discovery_effects.py` (1 -- comatose reads 0,
    real value untouched), `test_practice_execution.py` (2 -- Practice
    blocked while comatose, Tactical still works), `test_cast_execution.py`
    (10 -- King immunity, both halving triggers plus a full-chance
    control, both Berserk-counterattack outcomes via seeded real RNG
    since the Furia bonus-HP roll isn't ScriptedRandom-friendly, and 4
    Resurrection-cures-a-coma cases) -- 3350 passed total.
- **Phase 311**: contested-province priority for a double
  simultaneous *neutral*-province invasion -- previously unsourced/
  arbitrary processing order, flagged by the user. `Regolamento AK.txt`
  [7.6]/[7.7]: "In caso di doppia invasione simultanea di una provincia
  neutrale da parte di eserciti non alleati fra loro, ha la priorità
  l'esercito guidato dal personaggio con il coefficiente d'iniziativa
  più alto; a parità di iniziativa, ha la priorità l'esercito con il
  maggior numero di unità" -- both per the project owner's own
  clarification (initiative first, unit count as the tiebreak).
  - New `turn/initiative.py character_initiative(state, leader)`:
    the general, character-wide Initiative score -- quoted in full in
    the module docstring -- "la somma dei punteggi nei suoi vari
    Talenti, con Marcia contato 3 volte" (every `Ability`, summed via
    `turn/discovery_effects.py effective_skill_level()` so Discovery
    bonuses are folded in for free and a comatose leader ([[Phase 310]])
    reads 0 automatically, plus 2 *extra* copies of March's own level).
    Not to be confused with `turn/encounter.py`'s own narrower [5.0]
    per-combat-tactic "initiative" (`_acts_first()`), a different,
    already-implemented, single-round mechanic. Magic-item-derived
    Initiative bonuses are documented as confirmed-mechanic-no-sourced-
    magnitude and left out, the same gap this project already leaves
    open elsewhere (e.g. Naval's own union bonus).
  - `turn/battle_orchestrator.py fight_multi_attacker_battle()`: right
    after `group_attackers_into_battles()` produces its separate
    (non-united) groups, a new pre-loop step checks whether
    `province_coord` currently belongs to no kingdom at all
    (`ProvinceState.owner_kingdom_id is None` -- a genuinely neutral
    province, matching the rulebook's own scoping) and, if so and there's
    more than one group, stable-sorts them by (each group's own highest
    member `character_initiative()`, descending; that group's own total
    unit count, descending) before the existing fight loop runs. An
    enemy-owned province's multi-invasion is untouched -- falls through
    to the pre-existing arbitrary (caller-supplied) order, since [7.6]'s
    own wording is scoped to "provincia neutrale" specifically. The
    function's own docstring gained a "Phase 311 addendum" documenting
    this, right after the pre-existing paragraph that had flagged the
    gap as unsourced.
  - 7 new tests: `test_initiative.py` (4 -- zero for no skill data, the
    sum-plus-two-March-copies formula, Discovery bonuses folded in for
    free, zero for a comatose leader), `test_battle_orchestrator.py`
    (3 -- higher-Initiative group claims a neutral province first,
    equal-Initiative groups tiebreak on unit count, an enemy-owned
    province's multi-invasion keeps the caller's own unchanged order) --
    3357 passed total.
- **Phase 312**: a genuine, previously-unnoticed internal
  contradiction in `Regolamento AK.txt` itself, flagged directly by the
  user -- the body text at [5.6] says the Cautious flee bonus is +30%
  ("(NOVITA') I personaggi Cauti hanno il 30% in più di possibilità di
  fuggire", already implemented as `turn/search_execution.py
  WEAK_TEMPER_FLEE_CHANCE_BONUS` since Phase 286), but the rulebook's own
  closing "NUOVE REGOLE E MODIFICHE" appendix (line 3533) restates the
  same rule as "I Cauti hanno il +20% di possibilità alla fuga" -- ten
  points lower, and nobody had ever consciously noticed or decided
  between the two conflicting numbers. The user (project author), asked
  directly, confirmed **+30% is correct** -- no behavior change, since
  the code already implemented the body text's figure; this phase is
  purely about getting the conscious decision on record. Both the
  constant's own comment and the module docstring's Phase 286 paragraph
  gained a "Phase 312 addendum" quoting the appendix's conflicting text
  and recording the resolution.
  - 1 new test: `test_search_execution.py
    test_weak_temper_flee_chance_bonus_stays_at_the_body_texts_30_percent`
    -- a regression guard against the value silently drifting to the
    appendix's own +20% figure -- 3358 passed total.
- **Phase 313**: closes the treasure-looting gap flagged in
  `turn/encounter.py`'s own "Victory and Death's aftermath" ([5.9]) note
  -- "looting a vanquished foe's treasure, magic items changing hands"
  was never wired for a defeated *character* (only a guarded *feature*'s
  own hoard has been granted on a Search win since Phase 242). New
  `turn/encounter.py loot_defeated_leader(state, *, winner_id, loser_id)`
  transfers every `ItemInstance` the loser owned to the winner via
  `GameState.transfer_item()` (Phase 140's own registry) -- item
  ownership isn't tied to `GameState.leaders`, so it works regardless of
  whether it's called before or after `remove_leader()`. Wired into
  every site where character-vs-character personal combat kills the
  loser: `turn/challenge_execution.py execute_challenge()`, `turn/
  patrol_execution.py execute_patrol()`, `turn/pursue_execution.py`'s
  own armyless-combat branch, and `turn/cast_execution.py`'s Kill_Enemy
  Berserk-retaliation-on-failure (both outcomes) -- each result
  dataclass (`ChallengeExecutionResult`, `PatrolExecutionResult`,
  `PursueExecutionResult`, `CastExecutionResult`) gained a
  `looted_item_ids: list[int]` field for a future narration phase.
  **Deliberately not wired into army-vs-army battle deaths**
  (`turn/battle_orchestrator.py`) -- [5.9] is personal-combat vocabulary
  ("a vanquished foe"), and a defeated army's own commanding leader (if
  any) survives an ordinary battle loss; only personal combat actually
  kills the leader themselves, so that's the gap's real scope. King
  succession's own player-choice half (also named in that same [5.9]
  note) stays a separate, still-open gap, unaddressed here.
  - 6 new tests: `test_encounter.py` (3 -- transfers every item, returns
    empty when the loser owned nothing, works regardless of call order
    relative to `remove_leader()`), `test_challenge_execution.py`,
    `test_pursue_execution.py`, and `test_patrol_execution.py` (1 each,
    extending each module's own existing decisive-loser test with a
    looted item), plus 2 pre-existing `test_cast_execution.py` Berserk
    tests extended with loot assertions -- 3364 passed total.
- **Phase 314**: the exact hex-adjacency offset convention
  (`turn/movement.py`'s own "odd-r vs even-r, cannot be verified without
  the lost source" caveat) is now confirmed from real game data, not
  guessed. `Desktop/SE3__T*.K*` turn-report narrative text explicitly
  names each home province's 6 real neighbors by direction and hex
  number (e.g. Kingdom 2 Turn 0: "The province of Mongu belongs to
  thee. Looking to the northeast... Shasta (#304)... To the east
  lies... Moongard (#405)... Southeast of here lies... Big Sky
  (#306)... southwestern horizon... Transylvania (#206)... To the west
  there lies... Macondo (#205)... Northwest of here is Orielle
  (#204)" -- Mongu's own number, 305, independently confirmed by 5
  *other* kingdoms' own reports each separately naming it "Mongu
  (#305)"). Splitting each real hex number as ``(number // 100, number
  % 100)`` and comparing the resulting coordinate deltas against
  `_EVEN_ROW_OFFSETS`/`_ODD_ROW_OFFSETS` (the six offset *vectors*
  were always right -- CTBOTH.PAS's own confirmed 6-direction shape)
  showed they're keyed to the *opposite* `coord.y % 2` parity from what
  `neighbors()` previously checked -- confirmed across 5 separate real
  provinces (Mongu, Maplehaven, Limerick, Flying Fish Sea, Moonshine
  Sea; turns 0/1/4/9, 4 different kingdoms; 15 individual direction
  observations, zero contradictions). `neighbors()`'s own ternary is
  flipped accordingly; `_to_cube()` (used by `hex_distance()`) switched
  from the standard "odd-r" cube-conversion formula to "even-r" to
  match -- the two offset tables are unchanged, but which real-world
  parity each applies to (and therefore which textbook cube-conversion
  reproduces distance-1 to every real neighbor) flips along with it.
  This also resolves the previously-flagged "board reaches y=17, taller
  than the assumed 15-row height" puzzle from `turn/hex_numbering.py`'s
  own docstring: under this same real numbering, the number's *leading*
  digit group (which reaches into the teens in the sample data) lines
  up with `HexCoord.x`, not `.y`, so it was bounded by `width=30` all
  along, never actually violating `height=15`.
  - 9 pre-existing tests updated for the corrected parity (their own
    hardcoded expected coordinates flipped along with it, not a
    behavior regression): `test_movement.py`'s own ownership-tier
    tie-break test, `test_move_execution.py`'s 5 non-adjacent-chase
    tests (`INTERMEDIATE` moved from (1,2) to (0,2)) plus its own
    ownership-tier tie-break test, and `test_turn_processor.py`'s 3
    Defend-battle-loss tests (`DL_FIRST_ATTACKER_ORIGIN`/
    `DL_SECOND_COVERED`/`DL_SECOND_ATTACKER_ORIGIN` relocated to stay
    adjacent under the corrected scheme).
  - 3 new tests: `test_movement.py` (`test_neighbors_matches_mongus_
    own_6_real_neighbors`, `..._moonshine_seas_own_3_real_neighbors`,
    `..._limericks_own_3_real_neighbors`) -- asserting `neighbors()`
    directly against the real, narrative-sourced neighbor sets above,
    independent of this module's own offset tables -- 3367 passed
    total.
- **Phase 315**: re-derives `turn/hex_numbering.py`'s
  "width=10, 78-84% match" LMOVE hex-number hypothesis from scratch,
  using the project's own parser instead of a lost ad-hoc script. Every
  consecutive pair of LMOVE targets within a leader's final plan segment,
  across all 10 `AK3__T*.K1` files, gives a stricter 59-pair dataset
  (versus the original 93). Checked against `turn/movement.py`'s Phase
  314-confirmed adjacency parity: **50/59 = 84.7%**, holding up even
  though that parity was fixed *after* the original validation ran
  against the old, now-corrected offsets. An exhaustive width sweep from
  2 to 200 (not just the handful tried originally) confirms width 10 is
  decisively the best fit -- the next closest, width 9, scores only
  57.6%. Also tested and **ruled out**: hypothesizing that AK3's own
  move-file numbering shares SE3's confirmed `row*100+col` report-file
  province-numbering scheme (both filename families contain a "3", but
  they turn out to be unrelated) -- scores only 23.7%, decisively
  falsifying that plausible-looking shortcut. Row-parity remains
  genuinely too-close-to-call from AK3 data alone (50 vs. 52 of 59 under
  the corrected vs. old parity), so `turn/movement.py`'s narrative-
  sourced parity (stronger ground truth than a statistical fit on move
  targets) stays the documented default here too. No code behavior
  changes -- `decode_hex_number`/`encode_hex_number` and
  `EMPIRICAL_AK3_BOARD_WIDTH = 10` are unchanged; this is a
  documentation-only strengthening of the module's own empirical basis,
  plus a permanent regression test against real fixtures.
  - 4 new tests in `test_hex_numbering.py`:
    `test_real_move_file_lmove_pairs_yield_the_59_pair_dataset`,
    `test_width_10_matches_over_84_percent_of_real_lmove_pairs`,
    `test_width_10_decisively_beats_every_other_width_2_to_200`,
    `test_se3_report_style_row_times_100_plus_col_is_ruled_out_for_
    ak3_lmove` -- 3371 passed total.
- **Phase 316**: a research-only pass (no new parser code)
  into what's actually in `GW3__T1`'s post-province-block content
  (`parser/gw_world.py`'s own "differently-shaped record format after
  line ~2066" known gap, Phase 222). Splits into three sub-parts,
  separated by a 2-line marker and closed by a fixed `"255 0 0"` x 52
  terminator row:
  - **128 rows, 9 fields each -- tested and falsified as a Feature/
    Monster roster.** Looked plausible (fields 1-2 are valid `HexCoord`s
    on the confirmed 18x9 board), but the real feature instance numbers
    named in `SE3__T1.K2`'s own "ADVENTURE" section (Macondo's Monastery
    `F#114`; Mongu's Cave `F#2` and Crypt `F#17`) **never appear
    anywhere in `GW3__T1`** -- a clean, direct falsification against
    real ground truth, not just an unconfirmed lead. The field that
    looked like a sequential instance id turned out to be trivial
    (`255 + row_number`, a file-position counter). This block's real
    meaning stays unknown.
  - **218 rows, 10 fields each -- confirmed as a per-Hero table.**
    Field 1 is a governing Hero's own `leader_id` (`255` = empty slot),
    fields 2-3 are that Hero's current `HexCoord`. Verified two ways:
    the complete set of distinct real field-1 values matches this same
    file's own confirmed `GWProvinceRecord.governor_leader_id` set
    exactly, except every single-digit id (0-9, this project's own
    King-numbering range for a 9-kingdom game) is systematically
    absent -- Heroes only, Kings excluded; and Philo (`leader_id` 70,
    confirmed governing Transylvania at `HexCoord(1, 5)` since Phase
    222) appears at exactly `"70 1 5 ..."`, twice. The remaining 7
    fields (items carried? personal stats? commanded units?) are still
    unresolved.
  - Documented as a `"Phase 316 addendum"` in `parser/gw_world.py`'s
    own module docstring, so a future phase that wants to build a
    `GWHeroRecord`-equivalent parser doesn't re-walk the already-
    falsified Feature/Monster hypothesis from scratch.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after -- no test or source-code
    behavior changed, only a docstring addendum.
- **Phase 317**: refines Phase 316's own 218-row-block
  finding (still research-only, no new parser code), using all 12 real
  `GW3__T1..T12` snapshots rather than just `T1`. Comparing the same
  `leader_id` across turns overturns the "one row per Hero" reading:
  Guerin (`leader_id` 18) has 6 rows in `T3` and 9 in `T4` (all sharing
  his own current, turn-to-turn-moving `HexCoord`) -- and his real
  `AK3__T4.K1` move file shows exactly 2 real `RECRUIT` phases that
  turn, a genuine sourced correlation between row-count growth and real
  Recruit orders. Working (not yet confirmed) hypothesis: one row per
  *army* under that Hero's command, not one row per Hero -- fields 4-10
  would hold that army's own type/size/quality, echoing `ArmyType`'s
  already-confirmed 0-19 ordinal range, though no individual field is
  decoded with confidence yet (field 4 skews toward `1`/`BOWMEN` in the
  small samples checked so far, not a wide enough spread to be sure).
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 318**: research pass (no new parser code) on the
  kingdom/leader header block before the province-record block
  (`GW3__T1` lines 1-~1419) -- one record per kingdom, King then his
  Heroes back to back, each with Title/Epithet/real-player-name lines
  and one or more `"Action Plans:"` blocks already in
  `parser/k1_moves.py`'s own grammar. Confirmed against real letters:
  Kingdom "Babba Sissoko" 's King (character name "Uga-Buga Makumb",
  player "Andrea Ferrigno") matches `SE3__T1.K1`/`SE3__T2.K1` exactly,
  including an identically-truncated title (`"Master of the s"`) in
  both independently-generated sources. A leader's own numeric header
  line starts with his current `HexCoord` (King Babba Sissoko's own
  `"11 7 ..."` matches his real capital Piratum) and position 4 is his
  `leader_id`. The 33-field kingdom-level header line, compared across
  all 12 real `T1..T12` snapshots, yields a **confirmed in-game
  calendar**: position 3 (and 20) is the turn number 1-12 exactly;
  positions 14/15/16 are day/month/year, progressing plausibly from
  19/12/2006 to 25/5/2007, corroborated by `AK3__T1.K1`'s own real
  "Due: Jan. 2, 2007" move-sheet footer. Position 29's near-monotonic
  growth looked like treasury but is **ruled out** by direct comparison
  against `SE3__T1.K1`/`SE3__T2.K1`'s own real treasury lines (11, then
  22 -- far smaller than position 29's own trajectory); a cumulative-
  revenue reading is plausible, not confirmed. Also independently
  confirmed a real dynastic succession: by `T12`, Kingdom Babba
  Sissoko's King is `"Brian Gruber"`, not Andrea Ferrigno -- the
  kingdom name persists across rulers, and the new King reuses
  `leader_id` 0.
  - Documented as a `"Phase 318 addendum"` in `parser/gw_world.py`'s
    own module docstring -- a promising lead for a future phase that
    could close `turn/kingdom_bridge.py`'s own "populating a brand-new
    `GameState` from nothing at turn 0" gap, since a leader's starting
    coordinate and an already-parseable embedded Action Plan both live
    in this block.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 319**: confirms one more leader-header field and
  corrects two Phase 318 claims (still research-only, no new parser
  code), by comparing the same header line across *different* leaders
  in one turn rather than the same leader across turns. **Corrected**:
  position 4 is not `leader_id` -- King Bradipo I's real `leader_id`
  (2, confirmed via `SE3__T1.K1`'s "Bradipo I (#2)") doesn't match his
  own position-4 value (`0`, the same as Babba Sissoko's, whose
  `leader_id` genuinely is 0) -- that earlier match was coincidental.
  **Corrected**: there's no separate "Kingdom name" field distinct
  from a leader's own name -- `"Uga-Buga Makumb"` (read in Phase 318
  as King Babba Sissoko's own alternate character name) turns out to
  have its own, separate leader record later in the very same
  kingdom's block, making him a second, subordinate Hero, not the King
  under another name; every name in this block is simply *a leader's
  own name*, King or Hero alike. **Confirmed, 3-for-3 against real
  letters**: leader header position 3 is the `Race` ordinal (the same
  `models/race.py Race` enum the province block already uses) -- King
  Babba Sissoko (`3` = `Race.ORCISH`) matches `SE3__T1.K1`'s "a Orcish,
  Undead ruler"; King Bradipo I (`0` = `Race.HUMAN`) matches
  `SE3__T10.K1`'s "a Human ruler"; King Kwoth (`0` = `Race.HUMAN`)
  matches `SE3__T6.K1`'s "a Human ruler".
  - Documented as a `"Phase 319 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 318's own addendum, so
    a future phase sees the corrected reading first.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 320**: confirms a Gender marker on a leader's own
  long numeric line (still research-only, no new parser code). That
  line (Phase 318's own "long numeric line, still unresolved")
  actually starts with a single letter token, `"M"` or `"F"`, followed
  by a constant `10` (a structural marker, identical for both genders).
  In `GW3__T1`, 8 of 10 leaders are tagged `"M"` and exactly 2 are
  tagged `"F"` -- and those 2 are `"Giovanna d'Arco"` (Joan of Arc,
  under male player Alberto Clerici) and `"Circe"` (the Odyssey's
  sorceress, under male player Marco Calabresi, already confirmed as
  King #8's own kingdom in Phase 318) -- both unambiguously female
  in-game character names chosen by male real players, matching the
  `"F"` tag exactly; every `"M"`-tagged leader has a male or
  gender-neutral name. This project doesn't currently model character
  gender anywhere, so no enum was added -- deferred to whichever future
  phase actually consumes it. The long line's own third token varies
  leader to leader (`2`/`0`/`1012`/`892`/`764` across the 5 leaders
  checked) with no real-letter cross-check found yet; left unresolved
  rather than guessed.
  - Documented as a `"Phase 320 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 319's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 321**: records an open, unconfirmed structural
  lead (research-only, no new parser code, no confirmed finding) on
  the kingdom-level "doubled 30-value list" that appears once per
  kingdom, right after its own name. It splits cleanly into 15
  `(min, max)`-shaped pairs -- suggestively the same count as
  `models/race.py Race` (15 members) -- but this is **not confirmed**:
  a universal per-`Race` table would be identical across every
  kingdom's own file, and it isn't (Babba Sissoko's own list and
  Bradipo I's own list share no values). Whatever this is, it's
  kingdom-specific, not a fixed race-indexed constant. No real letter
  data specific enough was found to test an alternative reading.
  Also ruled out (not documented as its own bullet, folded into this
  phase): the leader header's own position 19, checked across all 10
  leaders in `GW3__T1`, is `27` for 9 of them and `26` for one -- too
  uniform to be a real per-leader stat, more likely a structural
  marker.
  - Documented as a `"Phase 321 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 320's own addendum, as
    an open lead rather than a resolved field, so a future phase
    doesn't mistake the "15 pairs" shape for a settled result.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 322**: confirms a leader's own trailing
  ~128-token line (following that leader's own `"Action Plans:"`
  section, before the next leader's name) is genuine dynamic
  per-turn state, not a static template -- still research-only, no
  new parser code, no confirmed field meaning. Comparing King Babba
  Sissoko's own line across all of `GW3__T1..T6` shows real, targeted
  change over time: position 16 moves `1` -> `2` then plateaus;
  several further positions switch on starting `T4`; at least two (38,
  42) keep climbing, reaching `3` by `T6`. `128` doesn't match the
  confirmed 162-province board, and no project enum has 128 members,
  so a direct index mapping isn't obvious; identifying which specific
  slot tracks which specific real event would need substantially more
  cross-referencing than this pass attempted.
  - Documented as a `"Phase 322 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 321's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 323**: corrects Phases 320/322 -- the `M`/`F`
  Gender line and the trailing ~128-token dynamic block are
  **King-only**, not universal to every leader (research-only, no new
  parser code). Both earlier phases implicitly described these as
  belonging to "a leader" in general because every example checked
  happened to be a King. A Hero's own record is leaner and has neither
  field: `name` / 30-value list / 25-field header / (blank) /
  `"Action Plans:"` -- no `M`/`F` line, no Title/Epithet/player-name,
  no trailing block. Confirmed 3-for-3 each way in `GW3__T3`: Kings
  Babba Sissoko, Bradipo I, and Kwoth all have the full block; Heroes
  Guerin, Arnulf, and Clarambald all have the lean form. So Gender
  (Phase 320) and the dynamic per-turn state (Phase 322) are both
  King-specific fields -- a future parser for this block would need
  two distinct record shapes, not one.
  - Documented as a `"Phase 323 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 322's own addendum, so
    a future reader sees the corrected King/Hero distinction rather
    than the earlier, overgeneralized reading.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 324**: extends Phase 323's King/Hero distinction
  to Phase 321's own "doubled 30-value list" (research-only, no new
  parser code). Kings carry the 60-token doubled list Phase 321
  described; Heroes carry a single, un-doubled 30-token list instead
  (e.g. Guerin's own list is exactly 30 tokens). Confirmed on a larger
  sample than Phase 323's own check: across `GW3__T3`, all 7 Kings
  found (Babba Sissoko, Bradipo I, Kwoth, Hokuto, Kahn, Circe,
  Agesilao) have the 60-token list; all 11 Heroes found immediately
  after them (Guerin, Arnulf, Clarambald, Kokocala, Lallipugh,
  Alexius, Ningarl, Saladin, Girard, Everard, Stonebrick) have the
  30-token list -- 18 for 18, no exceptions. Phase 321's own "15
  pairs" shape remains real and unconfirmed for Kings; it simply
  doesn't generalize to a Hero's own shorter, un-doubled list.
  - Documented as a `"Phase 324 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 323's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 325**: decodes a leader's own doubled skill-list
  and 25-field header from a genuine original game-host document (the
  user's own "FILE UTILE PER LEGGERE IL FILE GW.TXT", the manual
  procedure for Valhalla hall-of-fame registration) -- a direct source,
  not an inference (research-only, no new parser code). Two findings:
  1. The 30-value list (Phase 316/321/324) is 15 `(skill_level,
     aptitude)` pairs, one per `Ability`, in exact `Ability` enum
     order -- **supersedes Phase 321's own unconfirmed "possibly
     `Race`-indexed" speculation** and matches Phase 127's own prior
     `SkillTable` pair-shape resolution.
  2. Five previously-unlabeled 25-field-header positions are named:
     position 4 `S` (Special effects, value meaning still unknown);
     positions 5-6 `L L` (Liege lord id, `255`=none/`0`-`11`=owned by
     that King -- a candidate for the leader-to-kingdom-ownership gap
     open since Phase 224, partially checked against real `GW3__T3`
     data but not yet settled); position 7 `C` (Condition,
     `0`=Dead/`1`=Hired/`2`=Mercenary, matching
     `models/monster.py MonsterEngagementState`'s first three members);
     position 10 `A` (Alignment, exact match for
     `models/alignment.py ALIGNMENT_ORDINAL`'s `1`-`5` range, also
     explaining King Babba Sissoko's real "Undead" alignment as
     `UNDEAD=7`, outside that range); position 11 `T` (Temper, exact
     match for `models/temper.py Temper`'s `0`-`3` range).

  Also documents that the `VALHALLA.txt` archive's own manually-authored
  `M`/`F` + favorite-magic-item line is a distinct artifact from the
  live `GW*` file's own naturally-occurring `M`/`F` line (Phase
  320/322/323), and notes the document's 94-entry Magic Treasures name
  catalog for the record (out of scope for this parser).
  - Documented as a `"Phase 325 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 324's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 326**: corrects Phase 319's own reading of "Babba
  Sissoko" and "Uga-Buga Makumb" (research-only, no new parser code).
  Phase 319 concluded Uga-Buga Makumb is a Hero owned by King Babba
  Sissoko. Re-examining `GW3__T3`/`SE3__T1.K1` shows they are instead
  **two different Kings of two different kingdoms**: Uga-Buga Makumb's
  own `GW3` record is King-shaped (60-token doubled skill list, `M`/`F`
  line, trailing ~128-token dynamic block, Liege `255 255`), not
  Hero-shaped; the two records are followed by two different real
  player names (`Andrea Ferrigno` vs `Andrea Vitali`); and `SE3__T1.K1`'s
  own `CHARACTERS` roster is addressed to Uga-Buga Makumb as "My Lord"
  and lists him first with `leader_id 1`, the same `Kx`-suffix pattern
  already confirmed for `K2`/Bradipo I and `K3`/Kwoth -- Babba Sissoko
  doesn't appear in that roster at all, since he belongs to a separate
  kingdom (`#0`). The "diplomatic contact" paragraph both Phase 318 and
  319 read from literally describes two independent Kings interacting,
  not a King commanding his own subordinate Hero. Phase 318's own raw
  facts about Babba Sissoko (coordinate, `Race.ORCISH`, Undead
  alignment, "Master of the s" truncation, player Andrea Ferrigno) all
  remain accurate; only the relationship between the two named leaders
  was misidentified, first by Phase 318 (same person, two names) and
  then by Phase 319 (King and his own subordinate Hero).
  - Documented as a `"Phase 326 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 325's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 327**: upgrades the Liege field (Phase 325's own
  leader-header positions 5-6) from open lead to confirmed
  (research-only, no new parser code). Using each `SE3__T1.Kx` letter's
  own `CHARACTERS` roster as independent ground truth, all 27 named
  Heroes found in `GW3__T3` were cross-checked against their own real
  Liege value: 16 already-affiliated Heroes show Liege exactly equal to
  their own King's real id (Guerin/Teleko->1, Clarambald/Garin->3,
  Ningarl/Lexington->4, Tarsus/Marlon->5, Gladstone/Hume->6,
  Rolando/Hakim->7, Behemond/Duqaq->8, Tancred/Negumba->9); 6 Heroes
  unaffiliated or dead at both turn 1 and turn 3 correctly show `255
  255` (Eric, Lakes, Samantha, Odysseus, Reynald, Arnulf); and 5 Heroes
  unaffiliated/dead at turn 1 show a real Liege by turn 3 (Melantheus,
  Tao-Li->1; Helatia, Jamielle->8; Tiffany->7), fully explained by this
  project's own already-implemented Hire and Resurrection mechanics
  rather than being a contradiction. 27 for 27, zero unexplained
  mismatches.
  - Documented as a `"Phase 327 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 326's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 328**: tracks one Hero (Guerin) across all 12 real
  turns to isolate which remaining leader-header positions are truly
  dynamic (research-only, no new parser code). Falsifies position 4
  (`S`) as the letter roster's own "Ini" column -- it reads `0` for all
  27 Heroes checked, never varying, while "Ini" does. Reconfirms
  position 7 (Condition) at full scale: all 27 Heroes match Dead
  (`0`)/Hired (`1`)/Mercenary (`2`) exactly. Surfaces two new candidate
  leads: position 18 behaves like a non-decreasing counter (Guerin:
  `0,0,0,0,1,1,1,2,3,5,5,7` across T1-T12); position 22 behaves like an
  accumulating bitmask (Guerin: `2,6,7,7,7,71,71,71,199,199,199,199` --
  each jump adds exactly one new bit, never clears one). Also notes
  position 12 fluctuates non-monotonically and goes negative (rules it
  out as a counter/bitmask; more likely a spendable resource), position
  19 shows no discernible trend (possibly a per-turn-recomputed state),
  and position 8 is a per-leader constant that differs between leaders
  (Guerin always 48, Ningarl always 46).
  - Documented as a `"Phase 328 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 327's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 329**: falsifies both of Phase 328's own leading
  hypotheses for positions 18 and 22 against Guerin's own full
  narrative record (research-only, no new parser code). Position 22's
  `Ability`-named bit pattern isn't an ability-unlock bitmask: the
  `ELEMENTAL` bit turns on at `T9` while Guerin's own Elemental skill
  stays `0` for all 12 turns, and the `TACTICAL` bit turns on at `T3`
  while Guerin's own Tactical skill is still `0` too. Position 18 isn't
  a battle-victory or conquest counter either: cross-referencing every
  real conquest in Guerin's own letters against the position-18 delta
  shows conquests in `T2`/`T4`/`T6`/`T7` with no counter change, and a
  `+1` at `T9` despite a purely diplomatic letter with no battle at
  all. Both fields remain confirmed dynamic and non-decreasing, but
  their real trigger is unresolved; the office-holder Ofc_Pts/Rank
  score tables in the same letters (Phase 137) were spot-checked too
  and don't line up with either position either.
  - Documented as a `"Phase 329 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 328's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3371 passed) both before and after.
- **Phase 330 (current)**: `parser/gw_world.py parse_gw_leaders()` +
  `GWLeaderRecord` -- the first real parser code for the kingdom/leader
  header block (Phases 316-329 were all research-only), closing the
  leader-to-kingdom-ownership gap open since Phase 224. Scans for the
  leader-record shape itself (name line, 30/60-token all-integer skill
  list, 25-token all-integer header) the same "confirmed unique, no
  false positives" way `parse_gw_world` already finds province records;
  against the real `GW3__T1` fixture this finds exactly 100 records (10
  Kings, 90 Heroes). Extracts Race/Alignment/Temper/coordinate/skills
  (all already-confirmed fields) and `kingdom_id`: for a Hero, decoded
  directly from the Liege field (Phase 325/327); for a King, a *new*
  finding -- a King's own kingdom id equals the 0-indexed position of
  his own King-shaped record in file order, confirmed 8-for-8 against
  every King with an independently-known real id from `SE3__T1.Kx`
  letters. Also found and documented a real nuance while validating
  against all 100 records (not just the 27 named Heroes Phase 327
  checked): Condition (Hired) doesn't always imply a real Liege --
  three self-ruling local characters (Kokocala, Lallipugh, Alexius)
  read Hired with Liege `255`, confirmed independent via real letter
  narrative text.
  - `turn/kingdom_bridge.py sync_leaders_from_gw_world()`: a second,
    additive bridge function alongside the existing K1-based
    `sync_leaders_from_kingdom()`. Matches by name (same limitation as
    the K1-based sync -- a `GWLeaderRecord` has no `leader_id` either),
    only enriches existing `LeaderState`s. Sets
    Race/Alignment/Temper/skills/`is_king` for every match (data the
    K1-based sync could never supply at all), and `kingdom_id` for a
    matched Hero specifically -- including Heroes who never appeared in
    any submitted move file, something the K1-based sync alone could
    never populate. A matched King's own `kingdom_id` is left untouched
    (his GW3 record can't supply it; that's the K1-based sync's own
    job).
  - Ran the full suite before writing new tests (non-breaking check:
    3371 passed), wrote 9 new tests (5 in `test_gw_world_parser.py`
    against the real `GW3__T1` fixture, 4 in `test_kingdom_bridge.py`),
    ran the suite again (3380 passed).
- **Phase 331**: decodes 3 of Block B's own 7 unresolved
  trailing fields -- Race, ArmyType, Quality (research-only, no new
  parser code). Fixed a turn-alignment error first: `GW3__Tn` reflects
  the game's state at the *end of turn n-1*, not turn n. Cross-
  referencing Guerin's own Block B rows in `GW3__T3`/`GW3__T5` against
  his own real "Modified Quality" army tables in `SE3__T2.K1`/
  `SE3__T4.K1`: field 4 = `Race` (fixed per race-locked monstrous
  `ArmyType`, 8-for-8; varies 0-3 for humanoid types, matching real
  per-unit race text); field 5 = `ArmyType` ordinal (tallying rows by
  this field exactly reproduces the real army roster's type
  composition, both turns); field 6 = `Quality` (matched as a per-type
  multiset against real qualities, both turns, using each unit's own
  *base* Quality not the letter's separate race/terrain-adjusted
  "Modified Quality"). 15 of 15 individual values checked matched with
  zero exceptions. Field 8 checked and ruled out as `BASE_STRENGTH`
  (constant per `ArmyType` but doesn't match the Str column); fields 7,
  9, 10 remain unexamined.
  - Documented as a `"Phase 331 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 330's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3380 passed) both before and after.
- **Phase 332**: confirms field 7 as a Skeletal-army marker
  and finds partial (not fully resolved) structure for the rest of
  Block B's own remaining unexamined fields (research-only, no new
  parser code). `field7=3` occurs on exactly 3 of 259 `GW3__T3` rows,
  every one belonging to an Undead-aligned leader or a leader serving
  an Undead King (Teleko/Guerin, both serving Uga-Buga Makumb; Babba
  Sissoko himself) -- directly confirmed against real letter text for
  Teleko: his own `field7=3` row decodes to Elven/Bowmen/Average, and
  `SE3__T2.K1`'s own real army table lists exactly one such unit for
  him, `"96th Skel Bowmen -- Elf -- Average"`, the literal "Skel"
  prefix this project's own `ArmyState.is_skeletal` already models,
  sourced from `models/monster.py MonsterEngagementState`'s own
  `ZOMBOID=3` member. Also finds (not yet confirmed against real data)
  that `field7 in {1,3}` occurs only on led rows and `field7 in {0,2}`
  only on unled ones, with `0` common and `2` rare among the unled
  rows and a different Quality spread -- suggestive of "still kingdom-
  owned, unled" vs. genuine "mercenary," flagged as an open lead. Field
  9's lone `251` value is a strict subset of the unled `field7=0`
  rows, unexplained further; field 10 remains unexamined beyond its
  own `{0,1}` range.
  - Documented as a `"Phase 332 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 331's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3380 passed) both before and after.
- **Phase 333**: pushes fields 9 and 10 further, finds one
  real structural fact, leaves both fields' own specific values open
  (research-only, no new parser code). Field 9 is confirmed a genuine
  sub-field of field 7: it reads exactly `0` on all 213 rows where
  `field7` is `1`, `2`, or `3`, and only ever varies (`1`, `2`, `251`)
  on the 66 rows where `field7=0` (unled, "under the garrison
  commander"). Tested and ruled out as an explanation for that `{1, 2,
  251}` split: Quality, `ArmyType`, field 8, and a same-province
  stacking/sequence-index reading (every province with more than one
  `field7=0` row was checked directly, none shows a sequential
  pattern). Field 10 remains fully unresolved -- no further leads found
  beyond Phase 332's own "rare binary, no correlation" observation.
  Notes that cracking field 9's specific values likely needs a
  different technique than what worked for fields 4-7, since unled
  garrison rows carry no persistent identity to track turn-to-turn the
  way a `leader_id` does for led armies.
  - Documented as a `"Phase 333 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 332's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3380 passed) both before and after.
- **Phase 334**: tries tracking one province's own unled
  garrison across turns instead of one leader's own rows (research-
  only, no new parser code). `HexCoord(10,4)`'s own 3 unled rows are
  byte-for-byte identical between `GW3__T2` and `GW3__T3`, including
  field 9's own exact values (`1, 1, 251`, same order both turns) --
  rules out field 9 as a simple per-turn-incrementing counter, since
  it would have changed across two genuinely idle turns. The same
  coordinate's own led rows *did* change in that window (King Uga-Buga
  Makumb's own units, present at `T2`, gone by `T3`), confirming the
  snapshot itself is turn-sensitive -- the garrison's own stability is
  real, not a sampling artifact. By `GW3__T4` the coordinate has no
  Block B rows at all, consistent with `SE3__T4.K1`'s own real letter
  describing this exact province (`#1105`, "Jellyfish Sea") being
  newly conquered with a brand-new `"288th Garrison"` formed there --
  supporting "unled rows persist unchanged until conquest wipes and
  replaces them" as the real mechanic, though the new garrison's own
  row wasn't located in `GW3__T4`/`T5` to directly compare, left open
  rather than forced. Net: field 9 confirmed a persistent per-unit
  state, not a counter, but its own specific values remain
  undeciphered.
  - Documented as a `"Phase 334 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 333's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3380 passed) both before and after.
- **Phase 335**: pushes field 10 across all 12 real
  `GW3__Tn` turns at once (research-only, no new parser code), instead
  of the single `GW3__T3` snapshot Phase 332/333 checked. Corrects the
  earlier "0 or 1" reading -- `GW3__T12` shows a `2` for the first
  time. Finds a clean, zero-exception `ArmyType` gate: field 10 is
  non-zero only for the 10 "humanoid"/conventional `ArmyType`s;
  across all 12 turns combined, the "monstrous, race-locked" types
  (`DRAGON_WING`, `EAGLE_WING`, `WHALES`, `MERMEN`, `ENTS`, `TROLLS`,
  `WEREBEASTS` -- 780 rows total) show zero non-zero field 10 values,
  not one. `WARG_RIDERS` is a rare partial exception traced to
  essentially a single persistently-tracked real unit (Guerin's own
  `209th Warg Riders`). Also confirms field 10 is `0` for every row in
  `GW3__T1` (game start) and the count of non-zero rows grows
  monotonically turn over turn, consistent with a rarely-cleared
  per-unit flag. Tests and rules out "this unit fought a battle" as
  the trigger: three of Guerin's own rows flip `0` to `1` between `T9`
  and `T10` with zero combat reported in his own real `SE3__T9.K1`
  letter for that turn (only an illegal-move attempt, a failed
  Tactics roll, and a plague). Leaves an open, unconfirmed lead: a
  `T12` cluster of unled rows shows field 10 values of both `1` and
  `2` side by side, suggestive of an incrementing count rather than a
  one-shot flag.
  - Documented as a `"Phase 335 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 334's own addendum.
  - Non-breaking, documentation-only: full suite passed unchanged
    (3380 passed) both before and after.
- **Phase 336**: consolidates Block B into real parser code
  -- `GWArmyRecord`/`parse_gw_armies()` in `parser/gw_world.py`, the
  first code (not research-only) phase for this block. Locates Block B
  the same shape-scanning way `parse_gw_world`/`parse_gw_leaders`
  already locate their own blocks (exactly-10-integer-token rows,
  taking the one contiguous run); verified this run is the single,
  unambiguous one across all 12 real `GW3__Tn` samples. Exposes only
  the independently-confirmed fields as typed values
  (`commanded_by_leader_id`, `coord`, `race`, `army_type`, `quality`,
  `is_skeletal`) and keeps the three still-undeciphered trailing
  fields as plain, raw ints (`raw_field8`/`raw_field9`/`raw_field10`)
  rather than guessing. Surfaced and documented a real correction while
  testing against the committed `GW3__T1` fixture: Phase 332's own
  "field 7's Skeletal marker only appears on led rows" claim doesn't
  hold at `T1`, which has two unled Skeletal rows -- the marker and
  the led/unled split are independent bits, not coupled the way a
  single-turn (`T3`-only) sample suggested.
  - Documented as a `"Phase 336 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 335's own addendum.
  - Added 5 tests in `tests/test_gw_world_parser.py` against the real
    `GW3__T1` fixture (218-row count, Philo's own known Dwarven Axemen
    rows, the Skeletal-marker correction, raw-field preservation, and
    error handling). Full suite: 3380 passed before, 3385 after.
- **Phase 337**: closes field 7's own unled `{0, 2}` split
  left open since Phase 332/333 -- `2` is the "independent mercenary,
  available to Recruit" marker. Real letters carry an "independent
  mercenaries which you may Recruit" table (province, unit
  designation, race, quality) whenever a mercenary sits near a
  kingdom's own territory; cross-referencing **every one of the 85
  distinct (real-turn, province) sightings of this table across every
  `SE3__T0..T11.Kx` letter available** against the corresponding
  `GW3__T(n+1)` snapshot's own Block B rows gives **85 exact matches,
  zero exceptions** -- the row with `field7 == 2` at that coordinate
  always has the exact Race/ArmyType/Quality the letter lists.
  Resolves field 7's own full range: `0` unled kingdom-owned garrison,
  `1` led (normal), `2` unled independent mercenary (confirmed here),
  `3` Skeletal marker (Phase 332/336). `GWArmyRecord` gains
  `is_mercenary: bool`, set only for the confirmed `field7 == 2` case
  -- the same treatment `is_skeletal` got in Phase 336.
  - Documented as a `"Phase 337 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after Phase 336's own addendum.
  - Added 1 test in `tests/test_gw_world_parser.py` against the real
    `GW3__T1` fixture, cross-checked against `SE3__T0.K1`'s own real
    mercenary table. Full suite: 3385 passed before, 3386 after.
- **Phase 338**: closes the "populate a `GameState` from
  nothing" gap for the part that's actually recoverable from a single
  `GW3` file -- `parser/gw_world_bridge.py bridge_new_game_state()`.
  Before writing any code, tested and **falsified** two candidate
  techniques for recovering an arbitrary Hero's own real `leader_id`
  (coordinate-match against a personally-governed province; coordinate-
  match against Block B's own `commanded_by_leader_id`) against 5
  independently-confirmed real ids from earlier phases -- both fail
  (Kokocala, Guerin, Teleko, Ningarl all mismatch), since multiple
  Heroes legitimately share one coordinate at game start. Confirmed
  with the user: every King gets his own real, confirmed `leader_id`
  (`== kingdom_id`, Phase 330) and a real `KingdomState`/`LeaderState`;
  every Hero gets a synthetic negative `leader_id` (real name, race,
  alignment, temper, skills, coord, and kingdom_id/Liege -- just not
  the real numeric identity). Provinces reuse the existing
  `bridge_gw_world_provinces()`/`resolve_province_owners()` unchanged.
  Armies bridge for every unled row (owner = the province's own
  resolved owner) and every King-led row (owner = that King's own real
  id); a Hero-led row is left out (owner unconfirmable) and returned in
  the report rather than bridged with a guessed `kingdom_id` --
  `ArmyState.kingdom_id=None` is already reserved for "confirmed
  mercenary" (Phase 337's own `is_mercenary`), so reusing it for
  "unknown" would silently conflict with that meaning.
  `apply_confirmed_hero_ids()` re-keys a Hero's `LeaderState` from its
  synthetic id to a real one once the user supplies a name-to-id list,
  and retries every Block B row that had to be left out for exactly
  that Hero.
  - Documented as a `"Phase 338 addendum"` in
    `parser/gw_world_bridge.py`'s own module docstring, directly after
    the existing Phase 278 note.
  - Added 6 tests in `tests/test_gw_world_bridge.py` against the real
    `GW3__T1` fixture, including a regression test for a bug caught
    mid-implementation (an early draft used a re-identified Hero's own
    `leader_id` as his army's `kingdom_id`, instead of his own
    `kingdom_id`/Liege field -- only equal for a King). Full suite:
    3386 passed before, 3392 after.
- **Phase 339**: closes most of Phase 338's own "Hero id"
  gap after all, via a fixed name roster rather than any per-game
  technique -- `models/hero_roster.py STANDARD_HERO_ROSTER`, sourced
  from a project-original reference document the user supplied
  (`"Nomi (eroi) fino a #99.txt"`) listing all 98 Hero names this
  project's own AK game series draws from, each with a fixed id and
  sex, independent of which particular game it is. Verified against
  the real `GW3__T1` fixture before relying on it: 88 of its own 90
  Hero names match the roster exactly, at unique ids all in the
  `10-98` range; the 2 unmatched names (`Bagmore`, `Kitralus`) are both
  real entries in the user's own separate `VALHALLA NEUTRAL.txt` --
  exactly the roster's own documented "`#99`, arrived via VALHALLA"
  case, not a data error. Also **corrects a mistake surfaced while
  cross-checking the roster**: Phase 338's own "coordinate-matching
  fails for Kokocala" claim used an unconfirmed test-fixture id (`50`)
  as if it were her own confirmed real id; the roster gives her real
  id as `10`, which the coordinate-matching technique had actually
  found correctly -- corrected here rather than left to mislead a
  future reader (this project's own standing policy, Phase 55/153's
  precedent), though the broader "no *general* technique" finding
  still holds independent of this one corrected case. `bridge_new_game_
  state()` now assigns a roster-matched Hero his own real `leader_id`
  and `sex` directly; Phase 338's synthetic-id scheme becomes the
  fallback for the genuinely un-rostered case only. Army bridging's own
  King-only check generalizes to any leader with a real id (King or
  roster-matched Hero), so a Hero-led Block B row now bridges
  immediately too, no longer deferred to `apply_confirmed_hero_ids()`.
  - Documented as a `"Phase 339 addendum"` in
    `parser/gw_world_bridge.py`'s own module docstring, directly after
    the Phase 338 addendum.
  - Added 6 tests in `tests/test_hero_roster.py` and updated/added
    tests in `tests/test_gw_world_bridge.py` for the new roster-first
    behavior. Full suite: 3392 passed before, 3398 after.
- **Phase 340**: end-to-end validates `bridge_new_game_state()`
  against a real, non-T1 world file (`GW3__T5`), cross-checked against
  the real `SE3__T4.K1` letter for that same turn -- and in doing so,
  finds and fixes a real parsing bug every earlier phase's testing had
  missed. `parser/gw_world.py parse_gw_world()`'s own province-header
  regex hard-coded a token as a literal `0` because it happened to be
  `0` for all 162 provinces in the only file (`GW3__T1`) this regex had
  ever been checked against; against `GW3__T5` it silently dropped 3 of
  162 real provinces (Katmai, Maplehaven, Khalturin) whose own token
  was nonzero there. Loosened to accept any integer -- re-verified
  against all 12 real `GW3__T1`-`GW3__T12` files, each now yields
  exactly 162 provinces, with no false positives introduced.
  - With the fix in place, the rest of the `GW3__T5` run is a clean
    positive validation: all 162 provinces/10 Kings/90 Heroes bridge,
    every Block B army row resolves, and Kingdom 1's own name/race/
    alignment, Guerin's own kingdom/race/alignment/sex/location, two
    wandering Heroes' (Kokocala, Dracona) own real ids/races/sexes/
    locations, Guerin's own 9-army roster at the Falkland Sea (exact
    `ArmyType`/`Quality` match against the letter's "Normal Quality"
    column), and province ownership (Falkland Sea, Ark Royal Sea,
    Balearic Sea) all match the real letter exactly.
  - Added `tests/fixtures/world/G3/GW3__T5` (a second real, user-
    provided world-file snapshot, same precedent as `GW3__T1`).
  - Documented as a `"Phase 340 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after the Phase 337 addendum.
  - Added a regression test for the regex fix in
    `tests/test_gw_world_parser.py`, plus a new
    `tests/test_gw3_t5_end_to_end.py` with 7 tests covering the full
    chain against the real letter. Full suite: 3398 passed before, 3406
    after.
- **Phase 341**: decodes most of Block A (the 128-row, 9-field
  block that precedes Block B in a world file) -- the last major
  unresolved structural mystery in the `GW3` format, open since Phase
  316's own falsified Feature/Monster-roster hypothesis. Cross-checking
  Block A's rows against 8 real provinces' own ADVENTURE-section
  letters (14 Feature instances total: Dolphin, Ngara, Jerbilia,
  Birchwood, Pearlgate, Hollabrand, the Jellyfish Sea) gives a clean,
  zero-exception decode of 4 of the block's 9 fields, on top of the
  coordinate (fields 1-2, already known) and the trivial file-position
  counter (field 4, already known, Phase 316):
  - **Field 3 = the guarded `Treasure`'s own ordinal.** Phase 316's own
    "64 distinct low values vs. 64 rows at a mystery `67`/`68`" reading
    wasn't real-vs-filler at all -- `67`/`68` are themselves real,
    valid `Treasure` ordinals (`GOLD_HOARD_LARGE`/`GOLD_HOARD_HUGE`),
    and the 2 real *named* treasures spotted in the same letter sample
    (Birchwood's Temple/`Antennae of Psychic Blasting`, Pearlgate's
    Pyramid/`Reflector of Armies`) match their own `Treasure` ordinals
    exactly too.
  - **Field 6 = the guarding `Monster`'s own ordinal**, and **field 7 =
    the `FeatureType`'s own ordinal** -- both confirmed 14-for-14
    against the same letter sample, zero exceptions.
  - **Field 9 = the guarding `Monster`'s own `MonsterEngagementState`**
    (Phase 130) -- constant `MERCENARY` across all 128 of `GW3__T1`'s
    own rows, but real, valid values (`DEAD`/`BOLD`/`CALM`) appear
    across `GW3__T2`-`GW3__T12` as the game progresses.
  - Field 5 (a small, stable `2`-`10` range) and field 8 (a confirmed
    constant `0` across all 12 real turns) remain undeciphered --
    `GWFeatureRecord` keeps both as `raw_field5`/`raw_field8` rather
    than guessing.
  - New `GWFeatureRecord`/`parse_gw_features()` in `parser/gw_world.py`,
    following the same "scan for the block's own unique fixed shape"
    approach `parse_gw_armies()`/`parse_gw_world()` already use.
  - Documented as a `"Phase 341 addendum"` directly in
    `GWFeatureRecord`'s own docstring (Block A's own research history
    already lives across the Phase 316/340 module-docstring addenda,
    not repeated here).
  - Added 6 tests in `tests/test_gw_world_parser.py`. Full suite: 3406
    passed before, 3411 after.
- **Phase 342**: decodes the world file's own 33-value header,
  the first of several planned phases mining a genuinely new source --
  the user supplied a *static reverse engineering of `AKGEN.EXE` itself*
  (the original world-generator executable, Turbo Pascal 6.0/DOS,
  disassembled directly, not inferred from letters), plus machine-
  readable JSON catalogs extracted the same way. Confidence is "certain"
  for nearly every finding since it comes from the compiled program's
  own logic, re-verified against all 12 real `GW3__T1`-`GW3__T12` files.
  - New `GameType` enum (`TRIAL`/`NORMAL`/`EUROPE`/`EARTH`/`VALHALLA`/
    `ARCANES`) and `GWHeader`/`parse_gw_header()` in `parser/gw_world.py`
    -- all 33 header fields named and typed. Every field re-verified
    against the real corpus: `army_count` matches this project's own
    earlier "218 to 345" growth exactly; `game_turn` matches 1-12
    exactly; the due-date fields match this module's own earlier Phase
    318 calendar finding exactly (`19/12/2006` through `25/5/2007`).
  - Corrects two of this project's own prior guesses: header field 22
    was floated as a possible capacity selector -- it's actually the
    Pascal `gametyp` enum, unrelated to capacity. Field 31 does more
    than gate Block B's own 10th field (Phase 335) -- it also triggers
    a legacy leader/province migration.
  - Documented as a `"Phase 342 addendum"` in `parser/gw_world.py`'s
    own module docstring, directly after the Phase 340 addendum.
  - Added 5 tests in `tests/test_gw_world_parser.py`. Full suite: 3411
    passed before, 3415 after.
  - **Queued next from the same source**: correcting Phase 341's own
    Block A field names now that the same source identifies them as
    `trowner`/`trcharges`/`fdis` rather than a discarded counter and
    two raw fields; and an office/title-block parser (merit records +
    the final 52-office table).
- **Phase 343**: extends `GWLeaderRecord` with the 15 leader
  status-line fields this project never decoded (of the status line's
  own 22 real values, only 7 were previously captured) -- from the same
  `AKGEN.EXE` static reverse engineering as Phase 342.
  - New fields: `birth_coord`, `original_liege_raw`, `hiring_turn`,
    `general_merit`/`admiral_merit`/`defender_merit` (the missing data
    Phase 137's own Imperial-Office research needed and didn't have a
    parser for), `feature_discoveries`/`discovery_points`/`white_
    magic_service_points`, `experience_progress`, `sex_raw`,
    `sex_override_flag`, `unpaid_blackmail_penalty_exponent`, and
    `known_by_kings_mask` -- re-verified against the real `GW3__T1`
    fixture wherever possible (e.g. every King's own
    `known_by_kings_mask` reads exactly `1023` = `2**10 - 1` for this
    10-King game, exactly matching the disassembly's own claim).
  - A genuine cross-validation surfaced along the way, not just a field
    dump: `birth_coord` matches each leader's own current `coord` for
    79 of the 100 real leaders in `GW3__T1`, and the other 21 all read
    values far outside any plausible map coordinate. 21 is exactly
    `2*K + 1` for this 10-King game -- the same reserve Phase 342's own
    world-generation section describes for each King's own two unlanded
    "companions" plus one further reserved roster slot, none of whom
    ever become a province's own governor. Documented as a real,
    structural correlation, not treated as a parsing bug.
  - `sex_raw` is deliberately *not* wired to `models.sex.Sex`: it reads
    `0` for every one of `GW3__T1`'s own 100 leaders, including
    confirmed-female Heroes (Tao-Li, Dracona) -- so it isn't what
    actually determines a character's displayed sex under normal play,
    and no real nonzero example exists yet to confirm which value would
    mean which sex.
  - Documented as a `"Phase 343 addendum"` directly in
    `GWLeaderRecord`'s own docstring.
  - Added 3 tests in `tests/test_gw_world_parser.py`. Full suite: 3415
    passed before, 3418 after.
- **Phase 344**: corrects Phase 341's own `GWFeatureRecord`
  (Block A) field names using the same `AKGEN.EXE` static reverse
  engineering as Phase 342/343's own `gw_format.records.full_feature`
  JSON, which confirms the exact field order `fx, fy, treaslist,
  trowner, trcharges, fmonst, ftype, fdis, fstate`.
  - Renames: what Phase 341 discarded as a "trivial file-position
    counter" is really `trowner_raw` (Pascal name literally
    "treasure owner **or container**", kept ambiguous per the source);
    `raw_field5` -> `trcharges` (the treasure's own remaining charge
    count, an unsigned byte); `raw_field8` -> `fdis_raw` (Pascal name
    "discovery **or flags**", also ambiguous at the source, a `word`).
  - A genuine finding beyond the rename: `GW3__T1`'s 128 rows all read
    the unclaimed-treasure sentinel `trowner_raw == 256 + row_index`
    exactly (Phase 341's own "255 + row_number" observation, same
    value under 0- vs 1-indexing) -- but `GW3__T5`'s fixture supplies
    this project's first 2 real *claimed*-treasure examples: exactly 2
    of its 128 rows diverge from that sentinel, and those are *exactly*
    the only 2 rows whose `engagement_state` is `DEAD`. Both divergent
    values (`0`/`6`) are real, valid indices into that file's own
    leader list, and both land on a King (`Babba Sissoko`/`Kahn`) of
    the matching `kingdom_id` -- consistent with `trowner_raw`
    switching from the sentinel to the claiming leader's own id once
    the guardian is killed, though kept as a raw `int` (only 2 real
    examples, both Kings, not a confirmed general rule).
  - Documented as a `"Phase 344 addendum"` directly in
    `GWFeatureRecord`'s own docstring.
  - Added 3 tests in `tests/test_gw_world_parser.py`. Full suite: 3418
    passed before, 3421 after.
- **Phase 345**: the office/title-block parser -- the last
  item from the "GW format/parser" sub-plan the user approved
  (`GameType`/header/leader record/Block A rename/this), and the final
  block in a world file's own layout. New `GWOfficeMeritRecord`,
  `GWOfficeStateEntry`, and `parse_gw_offices()` in `parser/gw_world.py`,
  drawing on the same `AKGEN.EXE` source's
  `gw_format.records.office_merit`/`office_state_entry`.
  - Unlike every other block this module parses, this one *can't* be
    found by scanning for a unique row shape: a bare 3-token line (the
    merit-record row's own `tityp, tildr, tipts` shape) recurs
    incidentally 154 times elsewhere in `GW3__T1` alone, mostly other
    data that happens to tokenize to 3 integers. `parse_gw_offices()`
    instead uses the file's own fixed block order plus the header's
    own count: right after Block B's own army rows end, read exactly
    `GWHeader.office_merit_record_count` (header field 29, already
    named in Phase 342) 3-token lines, then the world file's own final
    line is always the 156-integer (52-triplet) office-state table --
    verified against both committed fixtures byte-for-byte (`GW3__T1`:
    0 merit records, matching its own header field exactly; `GW3__T5`:
    159, likewise exact).
  - `Office` (Phase 81's own 52-member enum) turned out to be an exact
    match for the state table's own 52-entry index and every real
    `office_code` seen in both fixtures' merit records -- no new enum
    needed.
  - A genuine cross-fixture finding: `GW3__T1`'s freshly generated
    world has every office's `previous_holder_raw` read the same `255`
    "nobody" sentinel this module's other leader-id fields already use,
    and every `known_by_kings_mask` read `0` -- but `GW3__T5` has real
    holders and real nonzero per-King bitmasks, confirming both fields'
    own semantics with a before/after pair rather than a single
    snapshot.
  - Documented as a `"Phase 345 addendum"` directly in
    `GWOfficeMeritRecord`/`GWOfficeStateEntry`'s own docstrings.
  - Added 5 tests in `tests/test_gw_world_parser.py`. Full suite: 3421
    passed before, 3426 after.
  - This closes the "Formato GW e parser (Block A/B, header, leader
    record)" sub-plan the user approved; the remaining AKGEN.EXE
    material (world generation from scratch, battle-luck engine
    corrections, Imperial Office/Royal Title exact formulas, 60-monster
    profiles, spell-catalog corrections, special-abilities-5-10
    assignment, Valhalla algorithm, and the Hero/province name-catalog
    discrepancy flagged back in Phase 341/342) is still untouched and
    needs a fresh prioritization round.
- **Phase 346**: the first of a new 6-phase sub-plan
  correcting `turn/battle_luck.py` and the rest of the battle-
  resolution pipeline against a *second* AKGEN-adjacent source -- a
  static reverse engineering of `AK.EXE`/`AK.OVR` (the real runtime
  battle resolver, not the `AKGEN.EXE` world generator Phase 342-345
  drew on), plus `RULES.AK`/`ADDEND.AK`/`RUMORS.PAS`/`SAY.PAS`/
  `BLUCK.X2`/`CLUCK.X2`/`CLUCK2.X2`/`TACTICS.X2`. This module's own
  pre-existing docstring said outright "every number is a deliberate,
  DOCUMENTED design choice, not a recovered rule... revisit these
  constants first if real game data or a recovered rule ever
  contradicts them" -- that trigger has now happened.
  - The real formula: one global luck value per side, drawn once per
    battle (`G1`/`G2`, each `U[0,1)`), and one local luck value per
    side, drawn fresh for every column (`L1`/`L2`). Side `s`'s own real
    per-column strength multiplier is `R_s = 1 + k*(G_s+L_s)`, `k`=0.75
    on turn 1 (range `[1,2.5)`, "because both random components are
    halved"), 1.5 on turn 2+ (range `[1,4)`) -- a materially higher
    ceiling than this project's own earlier guess (at most 1.5x column,
    1.1x battle), though still consistent with the rulebook's own "can
    as much as double... but most only... 1.5 or less" language for the
    *typical* draw.
  - New `draw_global_luck`, `draw_local_luck`, `luck_strength_
    multiplier`, `bluck_event_index` (`clamp(1,17,
    9+round(9*(G1-G2)))`), and `cluck_event_index`
    (`clamp(1,39, 20+round(20*(L_selected-L_other)))`) in
    `turn/battle_luck.py`. Both discretized narration-index formulas
    were verified empirically before being written: a 2,000,000-draw
    Monte Carlo of each matched the source's own declared per-index
    probability tables (turn-1 and turn-2+) to within 0.03 percentage
    points.
  - **Deliberately not yet wired into `resolve_battle`** -- `R_s` only
    means something once plugged into the real `BRES` column-scoring
    formula (`turn/battle_resolution.py`'s current win-decision path
    uses a different, older mechanism entirely: `roll_column_luck`/
    `roll_battle_luck`, still both untouched, plus a logistic win-
    probability estimate). Rewiring the win decision itself to the real
    `BRES` formula is next (queued as its own phase in this same
    sub-plan): mirrors this project's own established "implement the
    standalone function first, wire it into the real call site in a
    later phase" split (Phase 172/173 precedent).
  - Documented as a `"Phase 346 addendum"` in `turn/battle_luck.py`'s
    own module docstring.
  - Added 5 tests in `tests/test_battle_luck.py` (exact clamp/direction
    checks plus a 300,000-draw distributional cross-check against the
    source's own neutral-outcome percentages). Full suite: 3426 passed
    before, 3431 after.
  - **Queued next in this sub-plan**: column resolution (`BRES`
    formula, replacing the win/loss decision itself), direct
    destruction, pursuit, quality-change, and formation-multiplier
    corrections -- each its own phase, verified against the same
    source.
- **Phase 347**: the real column-resolution score (`BRES`),
  the same `AK.EXE`/`AK.OVR` source as Phase 346. New `column_bres()` in
  `turn/combat.py`, alongside `win_probability` -- whose own docstring
  already called itself "a documented approximation, not a sourced
  rule" for exactly the gap `BRES` now fills.
  - `BRES = clamp(-5,5, round(R1*sqrt(r) - R2/sqrt(r)))`, where
    `r = side1_strength / side2_strength` is the deterministic ratio
    (every non-luck modifier already applied) and `R1`/`R2` are Phase
    346's own `luck_strength_multiplier` outputs. Its *sign* is the
    real engine's own column-winner decision (not a probability draw),
    and its *magnitude* matters downstream too -- the source states
    directly: "the engine weighs the size of each column result, not
    merely the number of columns won."
  - Confirmed a genuine cross-validation in passing, not just a new
    formula: the source's own `confirmed_multipliers` (`defender`
    1.25, `nemesis_approx` 0.67) match this project's own pre-existing
    `turn/combat.py DEFENDER_BONUS`/`NEMESIS_PENALTY` (1.25, 2/3)
    exactly -- both already-implemented constants turned out correct,
    not just newly-discovered ones.
  - Also adds `turn/battle_luck.py break_bres_tie()`: the source's own
    tie-break rule for an exact-zero summed `BRES` ("repeated
    differences of fair coins") is implemented as literally as its own
    ambiguous wording allows -- draw one fair coin per side, repeat
    until they disagree -- documented as an honest reading rather than
    a silently-assumed alternative.
  - **Still not wired into `resolve_battle`** -- same reasoning as
    Phase 346: the real win decision needs `column_bres`'s own output
    threaded through 6 files' worth of consumers (`turn/battle_line.py`
    `estimate_win_probability`, `turn/battle_orchestrator.py`,
    `turn/pursuit.py`, `turn/encounter.py`,
    `report/turn_report.py`), so the rewire stays its own later phase.
  - Documented as a `"Phase 347 addendum"` in `turn/combat.py
    win_probability`'s own docstring, plus `column_bres`'s and
    `break_bres_tie`'s own docstrings.
  - Added 8 tests (5 in `tests/test_combat.py`, 3 in
    `tests/test_battle_luck.py`). Full suite: 3431 passed before, 3439
    after.
- **Phase 348**: direct destruction, the same `AK.EXE`/
  `AK.OVR` source as Phase 346/347. New `direct_destruction_probability()`
  in `turn/combat.py`, alongside `column_bres`.
  - `clamp(0,1, 0.25*(abs(BRES) + speed_delta))`, where
    `speed_delta = clamp(-1,1, winner_speed - loser_speed)` (`ArmyType`'s
    own `ARMY_TABLE[...].speed`, Phase 4) -- the probability that a
    column's own first-line loser is destroyed outright once `column_bres`
    (Phase 347) has decided the column. Verified against the source's own
    worked 5x3 margin/speed-delta table exactly (e.g. margin 4, speed
    delta +1 computes `1.25`, clamped to the table's own `100%`, not an
    impossible `125%`).
  - The source's own explicit warning is carried into the docstring
    verbatim rather than silently dropped: this is *only* the direct
    contest check -- a survivor can still be destroyed later in pursuit
    (Phase 349, queued next) or removed for want of a retreat
    destination, neither of which this function models. Eligibility
    (alive, first-line, the losing side, not already eliminated;
    "special unit types may divert the result") stays the caller's own
    responsibility -- the source gives a formula for the roll, not for
    eligibility itself.
  - Documented as a `"Phase 348 addendum"`-equivalent directly in
    `direct_destruction_probability`'s own docstring (no existing
    docstring needed correcting this time, unlike Phase 346/347's own
    superseded-guess pattern -- this is a genuinely new formula, not a
    replacement for an existing "documented approximation").
  - Added 3 tests in `tests/test_combat.py` (exact table cross-check,
    speed-delta clamping, range bounds). Full suite: 3439 passed before,
    3442 after.
- **Phase 349**: pursuit, the same `AK.EXE`/`AK.OVR` source as
  Phase 346-348, and -- unlike those three -- **wired straight into the
  real call site** (`turn/pursuit.py resolve_pursuit()`), not left
  standalone: pursuit only has one consumer
  (`turn/battle_orchestrator.py`), a small enough blast radius to
  correct in place this phase rather than defer.
  - Confirms two more of this project's own pre-existing constants
    exactly: `INFANTRY_PURSUIT_CHANCE`/`CAVALRY_PURSUIT_CHANCE` (25%/
    75%) match the source's own `manual_average_attempt_rate` verbatim
    -- a third instance of an earlier, undocumented guess turning out
    correct (after Phase 347's `DEFENDER_BONUS`/`NEMESIS_PENALTY`).
  - What the source corrects is the standstill formula: new
    `pursuit_destruction_probability(r_p)` (a real piecewise curve in
    `r_p` = pursuer strength / retreater strength, verified against the
    source's own five worked examples: `r_p`=0.8/1.0/1.25/1.5/2.0 ->
    22.5%/50%/77.5%/91.667%/100%) replaces the old generic
    `estimate_win_probability` logistic curve inside `resolve_pursuit`.
    New `draw_pursuit_random_multiplier` supplies the source's own
    `random_multiplier_each_unit` (independent `U[1,2)`), applied to
    the pursuer's own strength before computing `r_p` -- the source's
    wording doesn't say which side it lands on, so this is a documented
    reading, not a silently-assumed one.
  - Fixed a `ZeroDivisionError` the direct-ratio formula introduced for
    a strengthless retreater (e.g. a fully depleted unit) with the same
    zero-strength edge-case handling `estimate_win_probability`/
    `column_bres` already use.
  - Updated one existing RNG-scripted test
    (`test_pursuit_destroys_a_caught_retreating_army`) for the new
    per-pairing random-multiplier draw -- the same "new RNG consumption"
    category of fixup this project's own Phase 28 first established as
    expected when a battle subsystem's own draw count changes.
  - Documented as a `"Phase 349 addendum"` in `turn/pursuit.py`'s own
    module docstring.
  - Added 4 tests in `tests/test_pursuit.py`. Full suite: 3442 passed
    before, 3446 after.
  - **Queued next in this sub-plan**: quality-change and formation-
    multiplier corrections -- the last two phases against this same
    source.
- **Phase 350**: quality change, the same `AK.EXE`/`AK.OVR`
  source as Phase 346-349. New `base_quality_change_percent()`,
  `FORMATION_DIVISOR`, and `quality_gain_merit_multiplier()` in
  `turn/aftermath.py` -- whose own pre-existing docstring said outright
  "no numbers at all are given here... every constant in this module is
  a deliberate, unsourced design choice... revisit freely."
  - The real formula: `base_percent = 60 >> max(0, quality +
    formation_divisor - 2)` (an integer right-shift, not a division),
    `formation_divisor` one of `1`/`2`/`4`/`8` for front/second/third/
    fourth-and-later formation depth. Verified exactly against the
    source's own 4-depth x 6-quality worked table. A losing, selected
    front-line unit falls at exactly `base_percent` (Depleted excluded);
    a winning, selected unit rises at `base_percent *
    quality_gain_merit_multiplier(score)` (Elite excluded), the merit
    multiplier itself confirmed against the source's own table (`1.0`
    at score >= 0, `0.6`/`0.2` at `-1`/`-2`, `0.0` at `-3` or worse).
  - **Not yet wired into `roll_quality_change`/`turn/battle_orchestrator.py`'s
    6 call sites** -- unlike Phase 349's pursuit rewire, the real
    formula's own two inputs (which formation depth an army fought at,
    and its own per-unit merit score) aren't tracked anywhere in this
    project's post-battle aftermath code today. Wiring them in needs
    threading that state through `fight_battle`'s own battle-line
    bookkeeping first -- a separate, larger design phase, not a drop-in
    swap. Kept standalone and tested, mirroring Phase 346's own split.
  - Documented as a `"Phase 350 addendum"` in `turn/aftermath.py`'s own
    module docstring.
  - Added 2 tests in `tests/test_aftermath.py` (exact table
    cross-checks for both new functions). Full suite: 3446 passed
    before, 3448 after.
  - **Queued next in this sub-plan (the last phase)**: formation-
    multiplier corrections (strength-by-rank, and the source's own
    `confirmed_multipliers` cross-check against `turn/strength.py`'s
    existing constants).
- **Phase 351**: formation multipliers, the last phase in the
  6-phase `AK.EXE`/`AK.OVR` battle-resolution sub-plan (Phase 346-351).
  Unlike every earlier phase in it, **this one needed zero code
  corrections** -- every single constant the source's own
  `battle_engine.formation.strength_by_rank` and `column_resolution.
  confirmed_multipliers` tables give was already exactly right in this
  project's own pre-existing code:
  - `turn/combat.py line_contribution` (`1/2^depth`) already matches
    `strength_by_rank` (`[1.0, 0.5, 0.25, 0.125, 0.0625]`) and its own
    "each further rank is halved" / stacked-non-humanoid halving rule
    exactly -- already fully tested by Phase 6's own
    `test_line_contribution_halves_per_depth`.
  - `turn/strength.py MAX_EXPLORATION_ADVANTAGE` (0.25),
    `TACTICAL_BONUS_PER_LEVEL` (0.20), and `PHANTASMAL_ARMIES_BONUS_
    PER_LEVEL` (0.15) match `confirmed_multipliers`' own
    `exploration_max` (1.25), `tactical_or_naval_per_level` (1.2), and
    `phantasmal_per_caster_level` (1.15) exactly.
  - `turn/duel.py DUEL_DEMORALIZATION_MULTIPLIER` (0.75) matches
    `confirmed_multipliers.preliminary_duel_loser_led_units` exactly
    (already behaviorally locked in by Phase 45's own
    `test_apply_duel_demoralization_reduces_strength_25_percent`).
  - `turn/strength.py FANATICISM_CHANCE` (Divine 50%/Good 40%/Evil 25%)
    matches the source's own separate `special_events` table exactly.
  - `DEFENDER_BONUS` (1.25) and `NEMESIS_PENALTY` (2/3 ~= 0.67) were
    already confirmed back in Phase 347; this phase closes out the
    remaining five constants the same `confirmed_multipliers` dict
    names.
  - This closes the whole sub-plan with a clean result: every constant
    this project's own earlier work either sourced directly from the
    rulebook (formation halving, exploration/tactical/phantasmal/
    fanaticism percentages, duel demoralization) or was forced to guess
    without a source (BLUCK/CLUCK luck, `BRES` column resolution,
    direct destruction, pursuit standstill, quality change) has now
    been checked against the compiled game engine itself -- six
    genuine corrections/additions (Phase 346-350) and, in this last
    phase, unanimous confirmation that the rulebook-sourced numbers
    were implemented correctly all along.
  - Documented as `"Phase 351 addendum"` notes directly in
    `turn/combat.py line_contribution`, `turn/strength.py` (two
    locations), and `turn/duel.py`'s own docstrings.
  - Added 4 tests in `tests/test_strength.py` (the three multiplier
    maximums plus the fanaticism table) -- `line_contribution` and
    `DUEL_DEMORALIZATION_MULTIPLIER` needed no new tests, already
    covered exactly by Phase 6/45. Full suite: 3448 passed before, 3452
    after.
- **Phase 352 (current)**: the first phase of a new, 10-phase sub-plan
  porting `AKGEN.EXE`'s own world generator (a static reverse
  engineering, distinct from Phase 346-351's own `AK.EXE`/`AK.OVR`
  runtime battle resolver) -- new top-level package
  `src/ak_engine/worldgen/`, since this is a genuinely new subsystem
  (creating a fresh world from nothing) rather than a correction to the
  existing parse-and-replay engine. Full 10-phase plan: this RNG
  primitive; map/terrain generation; province race assignment;
  province tax; leader placement; recruit slots + initial armies;
  correcting Phase 242's own "no source survives" feature-generation
  guesses with the real formulas; magic-item/treasure placement;
  internal magical locations; hero talent/aptitude generation.
  - New `worldgen/pascal_random.py PascalRandom`: the real linear
    congruential generator `AKGEN.EXE` itself used --
    `RandSeed = (RandSeed * 134775813 + 1) mod 2**32` (`134775813` ==
    `0x8088405`, the historically documented real Borland Turbo Pascal
    multiplier, not a value this project chose) and `IRand = trunc(
    Random * 32768)`, both confirmed directly from the disassembly.
    Every later phase drawing on the same generator (feature
    generation, initial-army budgets, hero talent rolls) builds on this
    one primitive rather than re-deriving it.
  - **Deliberately not implemented**: the real DOS-clock startup seed
    (`INT 21h`/`AH=2Ch`) that seeds hero-talent generation -- the
    source confirms *that* it's clock-derived (and the real, stated
    consequence: hero skills aren't reproducible from `game_number`),
    but not the exact bit-packing formula combining the four clock
    words into one seed, so guessing one would be exactly the kind of
    unsourced invention this project avoids. `PascalRandom.__init__`
    takes an explicit seed instead -- callers needing reproducibility
    (tests, or the source's own *separately* confirmed
    `RandSeed = (50 * game_number) mod 2**32` special-ability reseed, a
    later phase's own concern) supply one directly.
  - **Verification caveat, stated honestly**: no known-seed/known-
    output trace from the real binary exists in the source material, so
    this can't be tested for byte-exact reproduction of the original
    DOS executable's own output stream. What is tested: determinism
    (same seed -> same sequence), the documented `[0, 32768)` range,
    and a 200,000-draw Monte Carlo landing close to the expected
    uniform mean -- the same empirical bar this project's own
    `random.Random`-based dice formulas already meet elsewhere.
  - Added 9 tests in `tests/test_pascal_random.py`. Full suite: 3452
    passed before, 3461 after.

## Setup

```
cd ak_engine
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows
pytest -v
```

## Known-unresolved semantics (TODO)

These are deliberately left as raw, unvalidated data in the model rather
than guessed, to avoid silently encoding a wrong interpretation. Each will
need cross-referencing against `HostAK/TP/DEF2.PAS` (`Read_Moves`) and the
rulebook before being turned into named, typed fields:

- `KingdomMoveHeader.raw_fields[1]` and `[2]` — vary between turns (0/1 and
  0/8/1020 observed); meaning unknown.
- `PlanSegment.sp` (the `SP:` field) — meaning unknown; always ends in the
  values seen in samples but not confirmed to always be a fixed shape.
- The exact meaning of the 31 integers on the skill-values line — expected
  15 ability pairs (30 values) based on `CTBOTH.PAS`'s `ability` enum, but
  every real sample file has exactly 31. The 31st value's meaning is
  unconfirmed; `SkillTable.pair_for_ability()` only interprets the first 30.
- ~~`parser/k1_moves.py` mis-parses a nested Hire/Charm/Resurrection
  plan~~ **fixed in Phase 18** — see that phase's note above for the
  fix; `PlanPhase.nested_plan` now holds the recovered embedded plan.
  ~~A Cast-triggered nested plan's `ActionPlan.leader_id` is always
  `None`~~ **fixed in Phase 23** (`turn/cast_decode.py` now decodes the
  spell, so a Charm/Resurrection cast's own target -- the nested
  character's real id -- is recoverable). ~~Nothing decodes/executes a
  nested plan's own contents~~ **fixed in Phase 23 (decode) and Phase 32
  (dispatch)** — see Phase 32's note above; a newly-hired or
  Charm-targeted character's own orders now dispatch the same turn.
- ~~**Hex adjacency scheme** (`turn/movement.py`) — the original adjacency
  code isn't in the available source (it lived in the missing main
  program). The module implements a standard "odd-r" offset hex grid,
  which is consistent with the 6 direction names confirmed in
  `CTBOTH.PAS` (`dirname`), but the exact offset convention is a guess and
  unverified. Revisit here first if movement behavior ever looks wrong
  against real game data.~~ -- **resolved by Phase 314**: the exact
  offset-to-parity convention is now confirmed directly from real
  `Desktop/SE3__T*.K*` turn-report narrative text (5 real provinces, 15
  individual direction observations, zero contradictions) -- see that
  phase's own note above for the full sourcing and the one-line parity
  fix it required (`neighbors()`'s own ternary, plus `_to_cube()`
  switching from "odd-r" to "even-r" to match).
- **Humanoid-army-type compatibility** (`models/army_type.py`
  `MONSTROUS_ARMY_RACE`) — the rulebook states plainly that monstrous army
  types (Dragons, Eagles, etc.) require their own race's province, and
  that any humanoid army type works in any humanoid province, but never
  says explicitly whether a *humanoid* type can be recruited in a
  *non-humanoid* (monstrous) province. This module assumes not (symmetric
  incompatibility) — a reasonable reading, not a verified rule.
- **"Beasts" nemesis matchup** (`models/army_type.py` `NEMESIS`) — the
  rulebook lists "Beasts" as a nemesis type for Lt/Hvy Cavalry and
  Chariots but never defines the term. Interpreted here as `{Elephants,
  Camel Corps}`, the table's two mounted "beast" units — a guess, not a
  quote.
- **`win_probability` curve** (`turn/combat.py`) — the rulebook gives only
  two data points (1:1 ratio → 50% win chance, 4:1 ratio → "assured"
  victory, without a number). The implemented `ratio / (ratio + 1)` curve
  hits the first anchor exactly but gives 80%, not "assured", at 4:1 — an
  approximation flagged in the function's docstring, not a sourced
  formula. Revisit if a real battle result ever contradicts it.
- **Battle luck event percentages/ranges** (`turn/battle_luck.py`) — the
  rulebook confirms random battle events exist and gives their *shape*
  ("Each random event can as much as double the strength of the affected
  force... The first random event affects the whole battle, while
  succeeding events affect a column") but no probabilities or magnitude
  ranges. `HostAK/TP/SAY.PAS`'s `_BLuck`/`_CLuck`/`_CLuck2` narrative
  hooks and the matching `HostAK/TP/PROSE/BLUCK.X2`/`CLUCK.X2` templates
  corroborate the *structure* (one whole-battle event, separate per-column
  events, qualitative "no effect" up to "tremendous" magnitude tiers) but,
  like the rulebook, give no numbers either. The specific values (75%/55%
  chances, ±10-50% column luck, +1-10% single-side battle luck) are a
  deliberate design choice made with the user, not a recovered rule.
- **`exploration_advantage_multiplier` scaling** (`turn/strength.py`) —
  the rulebook's only concrete data point is the 100%-vs-0%-explored case
  giving exactly the max +25%. Scaled linearly by the exploration-percent
  gap in between; a documented interpolation, not a sourced formula (same
  situation as `win_probability`'s curve).
- **Which ability feeds `combat_ability_multiplier`** (`turn/strength.py`)
  — the rulebook says Tactical Ability normally, Naval "in Sea
  provinces". The function itself is ability-agnostic (just applies
  +20%/level); the caller must pick which ability's level to pass based
  on terrain.
- **Cavalry classification for pursuit** (`turn/pursuit.py`
  `CAVALRY_TYPES`) — the rulebook never lists which army types count as
  "cavalry" for the 75%-pursuit-rate rule. Interpreted as the table's
  mounted/fast land types (Lt/Hvy Cavalry, Chariots, Camel Corps, Warg
  Riders); everything else (including overflight/naval types) uses the
  25% infantry rate.
- **Pursuit catching order** (`turn/pursuit.py resolve_pursuit`) — "army
  speed is the most important factor in catching the defenders" has no
  formula. Implemented as a deterministic pairing (pursuers matched
  against the slowest retreating units first), not a probability model.
- **Post-battle quality-change constants** (`turn/aftermath.py`) — the
  rulebook gives *zero* numbers here (unlike `win_probability`'s two
  anchors) — only qualitative direction ("may", "probably", "decreases as
  quality increases"). Every constant in this module is an undsourced
  design choice; treat the whole module as more speculative than
  everything else in this README.
- **Conquest + sea-battle movement-cost stacking** (`turn/conquest.py`)
  — the rulebook states the conquest extra-point and the sea-battle
  extra-point as two independent rules with no stated interaction for
  when both apply. Treated as additive (both deduct).
- **Multiple Contingents unite chances** (`turn/multiple_contingents.py`)
  — "very good chance" (same origin) and "probably... separate battles"
  (different directions) have no numbers; implemented as 85%/30%, a
  deliberate design choice.
- **Battle outcome judged at the side level, not per-column**
  (`turn/battle_orchestrator.py fight_battle`) — a side that loses every
  column is treated as fully defeated (destroyed, or retreat/disband);
  any other losing pattern (mixed, or a tie) leaves the province
  contested with no eliminations. The rulebook's own language ("the
  defeated army", "contested provinces") supports this reading, but it
  doesn't itself specify a per-column elimination rule for a *partially*
  losing side, so this is an interpretation.
- **What `fight_battle` leaves out of the strength calculation**:
  ~~the exploration-advantage special factor, fanaticism, and the
  desert-without-camels penalty aren't wired in~~ **fanaticism (opt-in,
  see Phase 35 above) and desert-without-camels are wired in now**.
  ~~Exploration-advantage stays unwired -- a genuine structural gap...
  `ProvinceState.explored_percent` is one shared value per province,
  with no per-kingdom split to compare "own vs. enemy" against~~ --
  **wired in as of Phase 69** via the new
  `ProvinceState.explored_percent_by_kingdom` (see that phase's own
  note above for exactly which kingdom each side reads and the
  documented "owner isn't auto-seeded at 100%" simplification).
  ~~Tactical/Naval-ability~~ **is** wired in (Phase 30), and ~~the
  nemesis penalty isn't applied~~ **is now applied too** (Phase 33, in
  `resolve_battle` itself rather than `fight_battle`'s own
  `compute_effective_strength` calls, since nemesis needs the real
  column pairings that only exist after line-up -- see Phase 33's note
  above for the column-pairing interpretation used). ~~The
  Tactical-ability *switch* mechanic itself is genuinely unwired~~ **is
  now wired too** (Phase 34, see above) -- `resolve_battle` reads the
  same terrain-aware ability level as the strength bonus and Duel
  tiebreak.
- **Attacker forced-retreat destination** (`fight_battle`
  `attacker_origin`) — when supplied, uses the rulebook-correct "back to
  the province invaded from, or adjacent to it" rule, but always picks
  the first candidate rather than a "best" one (none is defined); when
  omitted, falls back to the general nearest-friendly-neighbor logic
  instead, which is not what the rulebook actually specifies for a
  forced attacker retreat.
- **The LMOVE hex-number encoding itself** (`turn/hex_numbering.py`) —
  unlike every other assumption in this README, this one is backed by an
  empirical test against real move-file data, strengthened in Phase 315:
  width=10 now scores 84.7% (50/59) against `turn/movement.py`'s Phase
  314-confirmed adjacency parity, and is the decisive best fit across an
  exhaustive width sweep from 2 to 200 (next closest: 57.6%) -- far above
  the ~1-2% expected by chance. Phase 315 also ruled out one plausible
  alternative: AK3 LMOVE targets are NOT SE3-style `row*100+col` province
  numbers (23.7% match), despite both filename families sharing a "3".
  Still open: the exact board height (real data reaches y=17, taller than
  `turn/movement.py`'s assumed 15-row "normal" board -- this game series
  may simply use a different board size), which row-parity convention
  applies (genuinely too close to call from AK3 data alone -- 50 vs. 52
  of 59 -- though `turn/movement.py`'s narrative-sourced convention is
  used here too, being the stronger evidence), and what the ~15% of
  non-adjacent pairs represent (some are plausibly legitimate, e.g. a
  leader chasing a distant target; one suspiciously round jump, exactly
  170, might be a distinct sentinel value).
- **`is_native_to_province` approximated as race-compatibility**
  (`plan_dispatch._dispatch_recruit`) — the rulebook's real rule is
  "Each province has 1 or 2 army types that can be recruited from the
  populace", a specific per-province list `GameState`/`ProvinceState`
  doesn't carry. Approximated instead with
  `is_army_type_compatible_with_race()` (any humanoid type in a humanoid
  province, or an exact race match for monstrous types) -- looser than
  the real rule, so the double-cost path may trigger less often than it
  should in-game. `PlanPhase.extra[0]` (always `0` in every sample) is
  also still unconfirmed and unused.

## Not yet implemented (by design, this phase)

- ~~**Chasing a non-adjacent target** (rulebook [3.1]): moving towards a
  hex that isn't adjacent, through friendly territory, with tie-break
  priorities and a "stop chasing" condition — needs a pathfinding
  algorithm; `resolve_move()` raises `NonAdjacentMoveError` for now.~~
  **The chase-step pathfinding is implemented (Phase 78) and wired into
  `execute_move()` (Phase 85)** — see those phases' own notes above.
  `resolve_move()` itself still raises `NonAdjacentMoveError` for a
  direct, non-chase-aware call (unchanged, by design). Still open: the
  rulebook's own multi-phase persistence rule ("overrides orders in a
  subsequent phase only if the character is practicing") isn't wired
  into `turn/turn_processor.py` yet — see Phase 85's own note for the
  two plausible readings this project couldn't disambiguate further.
- **`plan_dispatch.py` dispatches 21 of 22 `ActionCode`s without raising
  `UnsupportedActionError`** -- its practical maximum (see Phase 27's
  note above). ~~LMOVE, EXPLORE, LEAVE, PICK_UP, RECRUIT (Phase 15),
  DISBAND (Phase 16), HIRE/FIRE (Phase 17), PRACTICE (Phase 44, always
  resolved as solo -- see that phase's note above), and (for
  Charm/Kill_Enemy only) CAST (Phase 29) run end-to-end with real
  `GameState` mutation; SEARCH (Phase 19), TRADE (Phase 20), CAST's
  other 10 spells (Phase 23/29), USE_MI (Phase 24), CHALLENGE/PURSUE
  (Phase 25), ASPY/DEFEND (Phase 26), and TRAIL (Phase 27) decode but
  don't mutate `GameState`~~ -- **stale as of Phase 153** (this bullet
  was never updated as each of these gaps closed; corrected here rather
  than left to mislead a future reader, the same policy Phase 55's own
  self-correction note above established). Actually current: LMOVE,
  EXPLORE, LEAVE, PICK_UP, RECRUIT (Phase 15), DISBAND (Phase 16),
  HIRE/FIRE (Phase 17), PRACTICE (Phase 44, always resolved as solo),
  SEARCH (executed Phase 132, see `turn/search_execution.py`'s own note
  below), TRADE/Give (executed Phase 132/133), CAST (13 of 25 base
  spells execute as of Phase 60, see that phase's own note above --
  Charm/Kill_Enemy since Phase 29), USE_MI (executed Phase 141), CHALLENGE
  and PURSUE (real combat/catch-up since Phases 50-54), ASPY (real
  report data since Phase 62), and TRAIL (real catch-up since Phase 52,
  dispatched since Phase 54) all run end-to-end with real `GameState`
  mutation now. Only **DEFEND**'s own per-phase dispatch stays
  decode-only (`decode_defend_phase(phase)`, no mutation) -- by design,
  not an oversight: its actual effects (reactive reinforcement, Phase
  57; battle-loss cancellation, Phase 72) are cross-leader rules applied
  by `turn/turn_processor.py` once per turn, not something a single
  phase's own dispatch call could apply in isolation. WAIT, NO_ACTION,
  and MOVE_ABORT
  (Phase 22) dispatch as bare no-ops. Only **Succ_Trail** raises
  `UnsupportedActionError` -- deliberately, by design, not as an
  oversight (see Phase 27's note above).
  - **Recruit's remaining gaps**: ~~the target leader who will command a
    newly recruited army isn't validated as co-located (or even as
    existing at all) before being assigned command~~ **fixed in Phase
    47** -- see that phase's note below. ~~the ally "Treat" order
    precondition for recruiting in allied territory isn't checked --
    `in_ally_territory` pricing/crediting applies whenever the province
    is simply owned by an ally, regardless of whether that ally issued
    a Treat order permitting it~~ **fixed in Phase 261** -- see that
    phase's own note above (`GameState.treat_permissions`/
    `has_treat_permission()`). ~~the "former home province, now an
    ally's" 4-unit bonus stays unmodeled~~ **fixed in Phase 262** -- see
    that phase's own note above (`FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT`).
    Still open: the rulebook's more specific "1-2 recruitable types per
    province" isn't tracked, only approximated via race-compatibility
    (see Phase 12's note above); and this project still never blocks
    recruiting in a non-owned, non-allied province at all.
  - **Hire's remaining gaps** (see Phase 17's note above): a Hero's own
    "required pay" (may be less than the offer, depends on
    temper/race/alignment compatibility -- `models/temper.py Temper`
    now exists as of Phase 82) -- **confirmed genuinely absent from the
    Pascal source as of Phase 161** (`LCost`, the one identifier tied
    to a Hero's per-turn/required pay, is called at four separate sites
    in `REPORTS.PAS` but never *defined* anywhere in the 13 available
    `.PAS` files -- the same missing-main-program category as
    `ACost`/`Tax_Base`/`Inv_Bonus`, Phase 158's own note above; no
    separate `Hire`-specific procedure survives either) -- **and closed
    anyway by Phase 162**, which designs and implements a formula from
    the player's manual text (alignment distance + temper match, 1-5
    gold) rather than transcribing Pascal source that doesn't exist --
    see that phase's own note above for the full derivation and its
    `turn/hire_pay.py required_pay()`. ~~Race compatibility~~ was
    explicitly excluded from the formula per the user's own
    instruction (only alignment distance and temperament) -- `LeaderState`
    does have a real `.race` field as of Phase 196, but that's beside
    the point, since the exclusion was a design choice, not a data
    gap. ~~A genuine "rare exception" bypass for wide alignment gaps
    (the rulebook: "In rare occasioni un Re può assoldare Eroi con un
    Allineamento distante più di due posizioni" -- not modeled as a
    random chance here, only as Charm/Resurrection's own already-real
    bypass routes) remains open, with no sourced formula~~ **fixed in
    Phase 264** -- see that phase's own note above
    (`RARE_ALIGNMENT_EXCEPTION_CHANCE`, a user-specified 15%, not a
    recovered rule). Recurring per-gameturn pay (only the one-time
    hiring charge is modeled, matching Recruit's own established
    simplification) remains open.
    ~~"Can't Hire a Hero who rules his
    own province" (no King flag)~~ **fixed in Phase 40** -- see below.
    ~~`run_leader_plan` doesn't dispatch a `PlanPhase.nested_plan`'s own
    phases~~ **fixed in Phase 32** -- a newly-hired hero's own orders now
    dispatch the same turn, provided he already has a `LeaderState` in
    `state` to enrich (see Phase 32's note above).
  - ~~**Disband's remaining gap**: no King/Hero distinction on
    `LeaderState` means co-location isn't enforced for anyone~~ **fixed
    in Phase 40** (see Phase 16's note above for context on the original
    gap, and Phase 40's note below for the fix).
  - ~~**Search's remaining gap** (see Phase 19's note above): decoded but
    entirely unapplied -- resolving it needs a personal, non-army
    Encounter/combat resolver (Steal/Melee/Fire/Flee/Scout tactic
    resolution, [5.2]-[5.8]) plus stochastic feature-content generation.
    `turn/encounter.py` (Phase 48) now provides a first slice of the
    former (Melee + Fire Arrow combat math only, not yet wired to
    Search itself -- see that phase's note below), so this gap is
    narrower than it was, not closed.~~ -- **stale as of Phase 153**:
    `turn/search_execution.py execute_search()` (Phase 132) closed this,
    reusing `turn/encounter.py`'s Melee resolver directly. Genuinely
    still open, by design, not oversight (see that module's own
    docstring): only 6 of 61 real monster species have sourced combat
    stats (`models/monster.py MONSTER_STATS`, RULES.AK's own "Monster
    Table" is explicitly partial -- not guessed at further), only a
    Melee-tactic Encounter Plan resolves (Fire Arrow needs an
    unsourced monster hit-chance formula, Scout/Flee/Steal need their
    own separate resolvers), and a win only sets `Feature.looted = True`
    -- no treasure-instance/magic-item-ownership model exists yet for
    [5.9]'s actual looting. A Cast/Use_MI/Give tactic's sub-object is
    also still just a raw int -- no decoded spell-id or magic-item-id
    table exists in this project yet to resolve it further.
  - ~~**Trade's remaining gap** (see Phase 20's note above): the whole
    module, not just execution -- `obj`/`extra`'s field meanings aren't
    confirmed, so there's nothing yet to safely execute even if a
    resolver existed.~~ -- **stale as of Phase 153**: Phase 132/133
    confirmed `target_leader_id` and rewrote `turn/trade_execution.py
    execute_give()` into the real Give mechanic, wired as real execution
    in `plan_dispatch.py`. The Kingdom-level "Treat" diplomacy order's
    other half (scientific-discovery exchange between Allies, [8.4]) was
    a separate system, still unparsed as an order file -- **stale as of
    Phase 272**: `turn/scientific_treaty.py execute_scientific_treaties()`
    closed it anyway by reusing Phase 261's own caller-populated
    `GameState.treat_permissions`, the same "no real order-file shape
    ever seen" workaround already used for that field's own [3.4] half.
  - ~~**Practice's remaining gap** (see Phase 21's note above):
    `GameState` now has a per-leader skill/aptitude table
    (`LeaderState.skills`, Phase 30), but nothing populates it from a
    real parsed move file yet (see Phase 30's note above), and Practice
    is still blocked by its other two gaps regardless -- province-level
    multi-character grouping and a dice-roll procedure this project has
    no Pascal source for.~~ **Executed as of Phase 44** -- see that
    phase's note above. The dice-roll procedure turned out to be fully
    sourced in `RULES.AK` (only the roll *sequencing* is a documented
    design choice); only province-level multi-character grouping stays
    genuinely unresolved, worked around via a documented conservative
    "always solo" approximation. ~~Tactical's army-quality-training
    variant and Sage's extra device-discovery roll are separate,
    still-unmodeled special cases~~ -- **stale as of Phase 263**: both
    rolls are wired (`turn/practice_execution.py execute_practice`/
    `execute_practice_tactical`, Phases 167/171/263). Tactical's own
    training-maneuvers table is now complete across all five Quality
    tiers (Phase 263, RULES.AK [6.1] quoted in full); Sage's own
    device-discovery roll fires (Phase 171) but the discovered device
    itself stays unmodeled, no item/effect system existing anywhere in
    this project to attach it to (see that phase's own note above).
    Multi-leader army pooling for Tactical stays a genuine, documented
    gap.
  - ~~**Cast's remaining gap** (see Phase 29's note above): only Charm
    and Kill_Enemy execute; the other 10 real spells' actual effects...
    need game-state logic not present anywhere in the available Pascal
    source~~ -- **13 of the 25 base spells execute as of Phase 60** (see
    Phases 59 and 60's own notes above), once `Regolamento AK.txt`
    supplied exact numbers `RULES.AK`/`ADDEND.AK` never gave, and
    `GameState.battle_graveyard` (Phase 60) gave Skeletal_Army and
    Bless's own addendum something to read/clear. **Still open**:
    Hide_Feature and Clairvoyance (blocked by their own distinct missing
    subsystem -- the unpopulated `Feature` stub and the "story event"
    model respectively), plus all 10 Personal-Combat-only spells, which
    need the general tactic-sequence combat engine `turn/encounter.py`'s
    own docstring already scopes out -- this also keeps Invisibility's
    own addendum ("+30% flee chance") unmodeled along with the base
    spell. The success/failure percentage roll (Phase 30) covers every
    executed spell uniformly, real once a caster has `LeaderState.skills`
    data, always-succeeds otherwise. The Trade-
    \>Cast rewrite for secret spells 25-34 is also unmodeled (confirmed
    to exist in Pascal, zero real examples).
  - **Use_MI's remaining gap** (see Phase 24's note above): deeper than
    Cast's -- there's no Pascal source for how item instances are even
    created, so `item_instance_id` can never be resolved to a concrete
    item/spell from this project's available data, not just "not
    executed yet". Zero real examples either.
  - ~~**Challenge/Pursue's remaining gap** (see Phase 25's note above):
    the King/Hero encounter-acceptance rules ([3.12]) and the Spy Table
    catch-up formula ([4.33], [3.16]) aren't modeled~~ -- **fully closed
    across Phases 50-56**: Challenge's acceptance rules and real Melee
    combat (`turn/challenge_execution.py`, Phase 50); Pursue's own
    single-phase catch-up-and-combat resolver (`turn/spy_table.py` +
    `turn/pursue_execution.py`, Phase 51); Pursue's army-vs-army
    catch-up fighting a real battle (`fight_battle` wired in, Phase
    53); both dispatching through real execution instead of decode-only
    (`plan_dispatch.py`, Phase 54); and mutual `mutual_encounter`
    detection across leaders (`turn/turn_processor.py
    _dispatch_mutual_encounter`, Phase 56). ~~**Still open**: Pursue's
    own persistent multi-phase chase state -- the rulebook's "for the
    rest of the turn" behavior. Phase 66 added `step_toward_target`/
    `advance_pursuit`, a standalone chase-step-and-reroll primitive
    (confirmed with the user as a deliberately narrow first slice, not
    the full subsystem), but it isn't auto-wired into
    `turn/turn_processor.py`'s phase loop~~ -- **the directed-chase case
    is wired in as of Phase 70**: an unresolved Pursue/Trail now
    genuinely preempts the leader's own later-phase orders and the chase
    continues phase by phase via `advance_pursuit`/`advance_trail`
    (`turn/turn_processor.py _continue_active_pursuits`, see that
    phase's own note below). ~~**Still open**: "Characters On Patrol"
    (self-targeting Pursue, [3.16])~~ -- **wired in as of Phase 71**
    (`turn/patrol_execution.py`, `turn/turn_processor.py
    _dispatch_active_patrols`, see that phase's own note below).
    ~~**Still open**: Defend's other cancellation trigger ("cancelled if
    he loses a battle")~~ -- **wired in as of Phase 72**
    (`turn/turn_processor.py _apply_defend_battle_loss`, see that
    phase's own note below). Zero real examples for either action
    either.
  - ~~**ASpy/Defend's remaining gap** (see Phase 26's note above):
    intelligence-report generation (ASpy) and reactive cross-province
    battle-triggering (Defend) both need `GameState`/battle-orchestrator
    logic that doesn't exist yet~~ -- **Defend's own reactive
    battle-joining shipped in Phase 57, and ASpy's report-data
    generation shipped in Phase 62** (`turn/aspy_execution.py`) -- see
    those phases' own notes above. **Still open for ASpy**: only the
    report's *opening sentence* renders as of Phase 63
    (`report/turn_report.py render_spy_report_opening()`, SPY.X) --
    the actual owner/adjacent-owners/recruitable-types/capital facts
    have no confirmed PROSE template anywhere in the available source
    (see Phase 63's own note above for the research trail), so they
    stay unrendered. ~~plus taxation reporting (no per-province
    tax-base model exists)~~ -- **stale, corrected in Phase 265**:
    taxation *is* real and rendered (Phase 253's own `tax_estimate` +
    `render_spy_tax_estimate()`), and as of Phase 265 is finally
    perturbed by [4.33]'s own Margin of Error, not the exact value.
    `obj`
    (`target_province`) still stays an unconverted, untrusted raw int
    for both actions -- Phase 62 sidesteps needing it for ASpy at all by
    reading the rulebook's own "he is actually in" text literally
    instead. Zero real examples for either action either.
  - ~~**Trail's remaining gap** (see Phase 27's note above): decoded but
    unexecuted~~ -- **Trail's catch-up resolution is now implemented**
    (`turn/trail_execution.py`, Phase 52), reusing Phase 51's Spy Table
    directly ([4.33]'s "Chance to Pursue **or Trail**" is one shared
    column). ~~**Still open**: the actual spied-on intelligence payload
    (Actions, race, temper, alignment, treasures, armies led) isn't
    assembled -- no report-generation system exists yet to route it to,
    and several of those fields (race, alignment, per-leader treasures)
    still don't exist on `LeaderState` at all~~ -- **stale, left
    uncorrected across several phases that actually closed this: all
    six of [3.17]'s named fields are real as of Phase 252** (`temper`/
    `treasures_owned`/`armies_led` Phase 159, `alignment` Phase 164,
    `race` Phase 165 via the target's own Kingdom, `actions` Phase 252
    via `turn/turn_processor.py run_turn()`'s own post-dispatch
    backfill), plus the King-target aggregate case (`KingIntelligence`:
    treasury/allies/controlled provinces, Phase 166 -- "enemies"
    deliberately left out, no positive hostile-diplomacy registry
    exists to source it from). `report/turn_report.py
    describe_trail_intelligence()` renders the whole payload into
    prose. See `turn/trail_execution.py`'s own module docstring for
    the full phase-by-phase account -- corrected here per this
    project's standing policy of fixing a stale note on discovery
    rather than leaving a future reader misled (Phase 55/153's own
    precedent). Succ_Trail
    is deliberately not decoded at all --
    concluded structurally impossible to receive in a player move file,
    not merely unimplemented; see `turn/plan_dispatch.py`'s module
    docstring for the full evidence trail (exhaustive `lactions[...] :=`
    assignment search across all 14 available `.PAS` files, zero sites
    found).
  - Pursuit and Duel are now wired into `fight_battle()` (Phase 28, see
    below); Multiple Contingents is available via the new
    `fight_multi_attacker_battle()`, ~~but not yet auto-invoked from
    `execute_move()`/`plan_dispatch.py`~~ **reachable from real
    multi-leader play as of Phase 45** via `turn/turn_processor.py
    run_turn()` -- see that phase's note below. ~~The
    "Fleets fighting on land provinces would generally be reduced to
    Depleted status instead of being eliminated" exception~~ **fixed in
    Phase 38** (see above) -- not to be conflated with Whales' own "zero
    strength off-sea, guaranteed Sea retreat" rule, fixed separately in
    Phase 37. ~~The non-humanoid rear-targeting nuance~~ **fixed in
    Phase 39** (see above) -- discovered along the way: the *separate*
    numeric-superiority outflanking rule that `column_strength`'s
    `outflank_second_line` parameter was originally built for ~~is still
    unwired, a distinct, still-open gap of its own~~ **wired in Phase
    64** (see above) -- its own related nemesis-selection nuance
    ("chosen at random" among several eligible units) ~~stays
    unmodeled~~ **partly closed in Phase 65** (see above): the overflight
    half (an opposing overflight unit stacked behind the front line
    widens nemesis eligibility against your rearward units) is wired;
    the outflanking half stays unmodeled, since `RULES.AK` gives no
    further text connecting it to nemesis eligibility specifically.
  - ~~**`fight_multi_attacker_battle()`'s own edge case**: separate
    (non-united) groups are resolved sequentially against whatever's
    left of the province's defenders; if an earlier group cleanly
    sweeps them, a later group calling `fight_battle()` against an
    empty defender list will raise `ValueError`. The rulebook doesn't
    say how simultaneous separate battles against the same defenders
    are meant to interact -- not fixed here.~~ -- **fixed in Phase 73**
    (see that phase's own note below).
  - ~~The duel *fight itself* [7.1] is still approximated, not resolved
    -- the separate "Special Encounter Plan" character-combat system
    [5.10] this would need isn't built~~ **a real Melee duel is now
    available as of Phase 49** (`turn/encounter.py`, opt-in via
    `use_real_duel_combat`) -- see that phase's note below;
    `estimate_win_probability`-based approximation (Phase 28's note)
    stays the *default* to avoid perturbing this project's existing
    scripted-`rng` test sequences. `tactical_ability` now reads a real
    skill level when the commander's `LeaderState.skills` is set
    (Phase 30), 0 otherwise.
  - ~~Contested-province state across multiple turns
    (`turn/contested_province.py`'s functions exist but nothing calls
    them from `execute_move()`/`fight_battle()`)~~ **the illegal-move
    check is wired in as of Phase 36** -- see above. ~~Still open: a
    contested result still just sets `ProvinceState.contested_by_kingdom_id`
    and stops there, with no automatic rebattle "in the next phase" --
    `turn/turn_processor.py run_turn()` (Phase 45) is now a real
    phase-by-phase, multi-leader orchestrator, but doesn't wire this
    specific mechanic in either~~ -- **the automatic forced-rebattle
    rule is wired in as of Phase 55** (`turn/turn_processor.py
    _dispatch_contested_rebattles`, see that phase's own note below) --
    this bullet was left stale (not struck through) when Phase 55
    shipped; corrected here rather than left to mislead a future reader.
- **Populating a brand-new `GameState` from nothing at turn 0** (see
  Phase 31's note above): `turn/kingdom_bridge.py` can only *enrich*
  `LeaderState`s that already exist -- there is no source anywhere in
  this project's available data (move files carry orders, not state) for
  a leader's starting location, a kingdom's race/alignment/home
  province, or its treasury, so a true "load this Kingdom for the first
  time" path remains unbuilt. Every `GameState` in this project's tests
  is still hand-built by its caller.
- **Feature discovery, monsters, treasures, rumors, battlefield reports**
  (rulebook [3.2]): `resolve_explore()` only computes the deterministic
  cumulative exploration percentage. Actually discovering *what* a
  province contains is stochastic content generation tied to the game's
  monster/treasure tables and prose templates (see
  `HostAK/TP/PROSE/*.X*` in the original zip) — a much later phase.
  ~~Battlefield reports~~ **the battle-outcome slice now renders as of
  Phase 61** (`report/turn_report.py`) -- see that phase's own note
  above for exactly which sentences (clash/winner/destroyed/pursued/
  retreated) and which caller-supplied names it needs. ~~Feature
  discovery, monsters~~ **`models/feature.py`/`models/monster.py` now
  give both a real type-and-instance shape as of Phase 75** -- see that
  phase's own note above. ~~but actually populating a game's feature
  roster (world generation), generating rumors, and resolving a Search
  are all still entirely unbuilt~~ **Search resolution now exists as of
  Phase 132, and world generation + the direct-discovery half of this
  rule now exist as of Phase 242** (`turn/world_generation.py`,
  `turn/exploration.py discover_features()`) -- see that phase's own
  note above for the full density/terrain/guardian/treasure design.
  ~~Only the *rumor* half of [3.2] ("about half... are true") remains
  unbuilt -- a separate discovery channel from direct Explore, whose
  selection/falsification logic has no surviving source either.~~ **The
  rumor mechanic now exists as of Phase 243** (`models/rumor.py`,
  `turn/rumor.py`), closing [3.2] in full -- see that phase's own note
  above for the trigger-chance table and the content/truth design.
  ~~No report renderer consumes a `Rumor` yet~~ **`describe_rumor()`
  now renders a `Rumor` into prose as of Phase 244** -- see that
  phase's own note above. ~~`HostAK/TP/PROSE/FINDFEAT.X`, the sibling
  in-person-discovery template (as opposed to heard-by-rumor), is
  still not wired to any renderer.~~ **`describe_feature_discovery()`
  now renders it as of Phase 245**, closing [3.2] in full on the report
  side too -- see that phase's own note above. Everything outside a
  fought battle besides Explore/Search is still unbuilt: the
  letter-report frame, financial report, and general exploration
  narrative all still need a turn-events log this project doesn't have
  yet.
## What's excluded from this phase

- `SE3__T*.K1` files: same extension as the move files, but these are
  actually generated turn *reports* (narrative prose), not move data — kept
  as future reference output for the report-generation phase, not used here.
- ~~`GW3__T*` files: a different, denser numeric format — not yet
  investigated.~~ **Stale as of Phase 222** (this bullet was never
  updated once real work started on this file family): the province-
  record block has a full parser and `GameState` bridge since Phases
  222-224 (`parser/gw_world.py`/`gw_world_bridge.py`) -- tax, terrain,
  race, recruiting types, coordinates, and owner resolution are all
  confirmed against real data. The content before and after that block
  (kingdom/leader headers with embedded Action Plans; a 128-row block
  falsified as a Feature/Monster roster; a 218-row block confirmed as a
  per-Hero `leader_id`+`HexCoord` table with 7 still-unresolved trailing
  fields) remains genuinely unexplored/only-partially-explored -- see
  Phase 316's own note above and `parser/gw_world.py`'s own module
  docstring for the details.
