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
  to `kingdom_id = None` without enforcing co-location (same
  Disband-style King-vs-Hero simplification, `LeaderState` still has no
  King/Hero distinction). Several rulebook nuances are explicitly not
  modeled here (no data/formula exists for them, same situation as other
  entries in the TODO section below): a Hero's own "required pay" (which
  may be lower than the offer and depends on unmodeled per-Hero
  temper/race/alignment compatibility), recurring per-gameturn pay (only
  the initial offer is charged, once), and "can't Hire a Hero who rules
  his own province" (no King flag to check against).
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
  What's still open: **nothing decodes/executes a nested plan's own
  contents** -- `turn/plan_dispatch.py run_leader_plan()` doesn't look at
  `PlanPhase.nested_plan` at all, so a newly-hired hero's own orders
  (now correctly *parsed*) still aren't automatically *dispatched*
  against `GameState` the same turn they're hired. Also, a
  Cast-triggered nested plan's `ActionPlan.leader_id` is always `None`
  (this project doesn't decode spell ids, so it can't tell a
  Charm/Resurrection cast from any other spell, let alone recover the
  resulting character's id) -- only Hire-triggered nesting has a real
  `leader_id`.
- **Hex adjacency scheme** (`turn/movement.py`) — the original adjacency
  code isn't in the available source (it lived in the missing main
  program). The module implements a standard "odd-r" offset hex grid,
  which is consistent with the 6 direction names confirmed in
  `CTBOTH.PAS` (`dirname`), but the exact offset convention is a guess and
  unverified. Revisit here first if movement behavior ever looks wrong
  against real game data.
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
- **What `fight_battle` leaves out of the strength calculation**: the
  exploration-advantage and Tactical/Naval-ability special factors,
  fanaticism, and the desert-without-camels penalty aren't wired in --
  they need per-battle context (leader ability values, a camel-unit
  check, alignment-based fanaticism rolls) the orchestrator doesn't
  collect yet. More importantly, **the nemesis penalty isn't applied
  either**: it depends on which specific unit ends up paired against
  which in a column, and that pairing only exists *inside*
  `resolve_battle` after line-up — by the time `fight_battle` calls
  `compute_effective_strength`, pairings aren't known yet. Properly
  fixing this needs `resolve_battle` to support a post-hoc,
  pairing-aware strength adjustment pass.
- **Attacker forced-retreat destination** (`fight_battle`
  `attacker_origin`) — when supplied, uses the rulebook-correct "back to
  the province invaded from, or adjacent to it" rule, but always picks
  the first candidate rather than a "best" one (none is defined); when
  omitted, falls back to the general nearest-friendly-neighbor logic
  instead, which is not what the rulebook actually specifies for a
  forced attacker retreat.
- **The LMOVE hex-number encoding itself** (`turn/hex_numbering.py`) —
  unlike every other assumption in this README, this one is backed by an
  empirical test against real move-file data (78-84% adjacency match
  across 93 real consecutive-move pairs, vs. ~1-2% expected by chance),
  not just a "reasonable reading" of rulebook text. Still open: the exact
  board height (real data reaches y=17, taller than `turn/movement.py`'s
  assumed 15-row "normal" board -- this game series may simply use a
  different board size), which row-parity convention applies (the two
  options scored within 1 match of each other on this sample, too close
  to call), and what the ~16-22% of non-adjacent pairs represent (some
  are plausibly legitimate, e.g. a leader chasing a distant target; a few
  suspiciously round jumps might be a distinct sentinel value).
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

- **Chasing a non-adjacent target** (rulebook [3.1]): moving towards a hex
  that isn't adjacent, through friendly territory, with tie-break
  priorities and a "stop chasing" condition — needs a pathfinding
  algorithm; `resolve_move()` raises `NonAdjacentMoveError` for now.
- **`plan_dispatch.py` dispatches 21 of 22 `ActionCode`s without raising
  `UnsupportedActionError`** -- its practical maximum (see Phase 27's
  note above). LMOVE, EXPLORE, LEAVE, PICK_UP, RECRUIT (Phase 15),
  DISBAND (Phase 16), and HIRE/FIRE (Phase 17) run end-to-end with real
  `GameState` mutation; SEARCH (Phase 19), TRADE (Phase 20), PRACTICE
  (Phase 21), CAST (Phase 23), USE_MI (Phase 24), CHALLENGE/PURSUE
  (Phase 25), ASPY/DEFEND (Phase 26), and TRAIL (Phase 27) decode but
  don't mutate `GameState` (see their notes above -- same decode-only
  status Recruit had before Phase 15); WAIT, NO_ACTION, and MOVE_ABORT
  (Phase 22) dispatch as bare no-ops. Only **Succ_Trail** raises
  `UnsupportedActionError` -- deliberately, by design, not as an
  oversight (see Phase 27's note above).
  - **Recruit's remaining gaps**: the recruiting leader must already
    exist as a `LeaderState` at the target province (no validation that
    a *co-located* character issued the order); the rulebook's more
    specific "1-2 recruitable types per province" isn't tracked, only
    approximated via race-compatibility (see Phase 12's note above); and
    the ally "Treat" order precondition for recruiting in allied
    territory isn't checked -- `in_ally_territory` pricing/crediting
    applies whenever the province is simply owned by an ally, regardless
    of whether that ally issued a Treat order permitting it.
  - **Hire's remaining gaps** (see Phase 17's note above): a Hero's own
    "required pay" (may be less than the offer, depends on unmodeled
    temper/race/alignment compatibility), recurring per-gameturn pay
    (only the one-time offer is charged), alignment-based hire refusal,
    and "can't Hire a Hero who rules his own province" (no King flag).
    Also, `run_leader_plan` doesn't dispatch a `PlanPhase.nested_plan`'s
    own phases (see Phase 18's note above) -- a newly-hired hero's own
    orders are now correctly *parsed*, not lost, but still aren't
    automatically *executed* the same run.
  - **Disband's remaining gap**: no King/Hero distinction on `LeaderState`
    means co-location isn't enforced for anyone (see Phase 16's note
    above) -- a Hero should arguably need to be with the army to disband
    it, a King shouldn't.
  - **Search's remaining gap** (see Phase 19's note above): decoded but
    entirely unapplied -- resolving it needs a personal, non-army
    Encounter/combat resolver (Steal/Melee/Fire/Flee/Scout tactic
    resolution, [5.2]-[5.8]) plus stochastic feature-content generation,
    neither of which exist yet. A Cast/Use_MI/Give tactic's sub-object is
    also just a raw int -- no decoded spell-id or magic-item-id table
    exists in this project yet to resolve it further.
  - **Trade's remaining gap** (see Phase 20's note above): the whole
    module, not just execution -- `obj`/`extra`'s field meanings aren't
    confirmed, so there's nothing yet to safely execute even if a
    resolver existed. The Kingdom-level "Treat" diplomacy order
    (scientific-discovery exchange between Allies, [8.4]) is a separate,
    entirely unstarted system -- not parsed, not modeled, no real data
    available yet either.
  - **Practice's remaining gap** (see Phase 21's note above): needs a
    per-leader skill/aptitude table in `GameState` (only the King's is
    currently parsed at all, and only from the move file, not persisted
    into `GameState` either), province-level multi-character grouping,
    and a dice-roll procedure this project has no Pascal source for --
    the largest remaining gap of any decoded-but-unexecuted action so
    far, data-model-wise.
  - **Cast's remaining gap** (see Phase 23's note above): every spell's
    actual effect (province/character/army mutation) needs game-state
    logic not present anywhere in the available Pascal source -- only
    the id/target/nesting *shape* is known, not the mechanics. The
    Trade-\>Cast rewrite for secret spells 25-34 is also unmodeled
    (confirmed to exist in Pascal, zero real examples).
  - **Use_MI's remaining gap** (see Phase 24's note above): deeper than
    Cast's -- there's no Pascal source for how item instances are even
    created, so `item_instance_id` can never be resolved to a concrete
    item/spell from this project's available data, not just "not
    executed yet". Zero real examples either.
  - **Challenge/Pursue's remaining gap** (see Phase 25's note above):
    the King/Hero encounter-acceptance rules ([3.12]) and the Spy Table
    catch-up formula ([4.33], [3.16]) aren't modeled -- same missing
    non-army Encounter resolver as Search. Zero real examples for
    either either.
  - **ASpy/Defend's remaining gap** (see Phase 26's note above):
    intelligence-report generation (ASpy) and reactive cross-province
    battle-triggering (Defend) both need `GameState`/battle-orchestrator
    logic that doesn't exist yet, plus `target_province` staying an
    unconverted raw int until the hex-numbering-vs-`XMULT` question is
    resolved. Zero real examples for either.
  - **Trail's remaining gap** (see Phase 27's note above): decoded but
    unexecuted, same missing turn-simulation engine as everything else
    in this list. Succ_Trail is deliberately not decoded at all --
    concluded structurally impossible to receive in a player move file,
    not merely unimplemented; see `turn/plan_dispatch.py`'s module
    docstring for the full evidence trail (exhaustive `lactions[...] :=`
    assignment search across all 14 available `.PAS` files, zero sites
    found).
  - Pursuit, duels, and Multiple Contingents (all exist as standalone
    modules from Phase 8) aren't called from `fight_battle()` yet, nor is
    the "Fleets fighting on land are reduced to Depleted instead of
    eliminated" exception or the non-humanoid rear-targeting nuance [7.2].
  - The duel *fight itself* [7.1] — needs the separate "Special Encounter
    Plan" character-combat system [5.10], not built.
  - Contested-province state across multiple turns
    (`turn/contested_province.py`'s functions exist but nothing calls
    them from `execute_move()`/`fight_battle()` -- a contested result
    just sets `ProvinceState.contested_by_kingdom_id` and stops there).
- **Feature discovery, monsters, treasures, rumors, battlefield reports**
  (rulebook [3.2]): `resolve_explore()` only computes the deterministic
  cumulative exploration percentage. Actually discovering *what* a
  province contains is stochastic content generation tied to the game's
  monster/treasure tables and prose templates (see
  `HostAK/TP/PROSE/*.X*` in the original zip) — a much later phase.
## What's excluded from this phase

- `SE3__T*.K1` files: same extension as the move files, but these are
  actually generated turn *reports* (narrative prose), not move data — kept
  as future reference output for the report-generation phase, not used here.
- `GW3__T*` files: a different, denser numeric format — not yet investigated.
