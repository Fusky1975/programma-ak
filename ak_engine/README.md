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
  depends on unmodeled per-Hero temper/race/alignment compatibility),
  recurring per-gameturn pay (only the initial offer is charged, once).
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
    once per resulting group. **Not automatically invoked from
    `execute_move()`/`plan_dispatch.py`** -- `run_leader_plan` resolves
    one leader's moves at a time and has no notion of "wait for every
    other leader's same-phase move before resolving a battle," which
    real detection would need; available for any caller that already
    has several simultaneous attacks assembled. Two more documented
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
  - **Practice ([3.13]) is still not executed** despite now having the
    ability-data piece it was missing -- see Phase 21's note above and
    the "Not yet implemented" section below: its other two gaps
    (province-level multi-character grouping, and a dice-roll procedure
    with no available Pascal source) are untouched by this phase, so it
    stays decode-only.
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
    turn-loop restructuring (`turn/plan_dispatch.py run_leader_plan`
    processes one leader's phases at a time, with no notion of
    "re-trigger a battle here next phase regardless of what this leader
    ordered") well beyond this phase's scope.
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
  - **Druidic-ability carve-out not modeled**: "if the non-human unit
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
    here.
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
  - **Not extended to `battle_line.py`'s rear-targeting carve-out**
    (still open, see Phase 39/41's notes above) -- this phase only
    closes the quality-penalty gap for unled armies, not the separate
    "held back from rear-targeting" behavior tied to the same rulebook
    sentence.
  - Non-breaking: full suite passed unchanged (845 passed) immediately
    after wiring, before any new tests were written. 5 new tests added
    (850 passed total).

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
- **What `fight_battle` leaves out of the strength calculation**:
  ~~the exploration-advantage special factor, fanaticism, and the
  desert-without-camels penalty aren't wired in~~ **fanaticism (opt-in,
  see Phase 35 above) and desert-without-camels are wired in now**.
  **Exploration-advantage stays unwired** -- a genuine structural gap,
  not a missing-context oversight: `ProvinceState.explored_percent` is
  one shared value per province, with no per-kingdom split to compare
  "own vs. enemy" against (see Phase 35's note above).
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
  DISBAND (Phase 16), HIRE/FIRE (Phase 17), and (for Charm/Kill_Enemy
  only) CAST (Phase 29) run end-to-end with real `GameState` mutation;
  SEARCH (Phase 19), TRADE (Phase 20), PRACTICE (Phase 21), CAST's other
  10 spells (Phase 23/29), USE_MI (Phase 24), CHALLENGE/PURSUE (Phase
  25), ASPY/DEFEND (Phase 26), and TRAIL (Phase 27) decode but don't
  mutate `GameState` (see their notes above -- same decode-only status
  Recruit had before Phase 15); WAIT, NO_ACTION, and MOVE_ABORT (Phase
  22) dispatch as bare no-ops. Only **Succ_Trail** raises
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
    (only the one-time offer is charged), and alignment-based hire
    refusal. ~~"Can't Hire a Hero who rules his own province" (no King
    flag)~~ **fixed in Phase 40** -- see below.
    ~~`run_leader_plan` doesn't dispatch a `PlanPhase.nested_plan`'s own
    phases~~ **fixed in Phase 32** -- a newly-hired hero's own orders now
    dispatch the same turn, provided he already has a `LeaderState` in
    `state` to enrich (see Phase 32's note above).
  - ~~**Disband's remaining gap**: no King/Hero distinction on
    `LeaderState` means co-location isn't enforced for anyone~~ **fixed
    in Phase 40** (see Phase 16's note above for context on the original
    gap, and Phase 40's note below for the fix).
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
  - **Practice's remaining gap** (see Phase 21's note above): `GameState`
    now has a per-leader skill/aptitude table (`LeaderState.skills`,
    Phase 30), but nothing populates it from a real parsed move file yet
    (see Phase 30's note above), and Practice is still blocked by its
    other two gaps regardless -- province-level multi-character grouping
    and a dice-roll procedure this project has no Pascal source for.
  - **Cast's remaining gap** (see Phase 29's note above): only Charm and
    Kill_Enemy execute; the other 10 real spells' actual effects
    (province/army mutation, mostly) need game-state logic not present
    anywhere in the available Pascal source -- only the id/target/
    nesting *shape* is known for them, not the mechanics -- and
    Resurrection specifically can never be executed without a
    dead-leader registry this project doesn't have. The success/failure
    percentage roll is now real for Charm/Kill_Enemy (Phase 30), but
    only takes effect once a caster has real `LeaderState.skills` data
    (see Phase 30's note above); it isn't modeled at all for the other
    10 spells, since they aren't executed in the first place. The Trade-\>Cast rewrite
    for secret spells 25-34 is also unmodeled (confirmed to exist in
    Pascal, zero real examples).
  - **Use_MI's remaining gap** (see Phase 24's note above): deeper than
    Cast's -- there's no Pascal source for how item instances are even
    created, so `item_instance_id` can never be resolved to a concrete
    item/spell from this project's available data, not just "not
    executed yet". Zero real examples either.
  - **Challenge/Pursue's remaining gap** (see Phase 25's note above):
    the King/Hero encounter-acceptance rules ([3.12]) and the Spy Table
    catch-up formula ([4.33], [3.16]) aren't modeled -- same missing
    non-army Encounter resolver as Search. `LeaderState.is_king` (Phase
    40) now exists, so the *data* this rule would need is no longer
    missing, only the encounter-resolution system itself. Zero real
    examples for either either.
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
  - Pursuit and Duel are now wired into `fight_battle()` (Phase 28, see
    below); Multiple Contingents is available via the new
    `fight_multi_attacker_battle()` but not yet auto-invoked from
    `execute_move()`/`plan_dispatch.py` (see Phase 28's note). ~~The
    "Fleets fighting on land provinces would generally be reduced to
    Depleted status instead of being eliminated" exception~~ **fixed in
    Phase 38** (see above) -- not to be conflated with Whales' own "zero
    strength off-sea, guaranteed Sea retreat" rule, fixed separately in
    Phase 37. ~~The non-humanoid rear-targeting nuance~~ **fixed in
    Phase 39** (see above) -- discovered along the way: the *separate*
    numeric-superiority outflanking rule that `column_strength`'s
    `outflank_second_line` parameter was originally built for is still
    unwired, a distinct, still-open gap of its own.
  - **`fight_multi_attacker_battle()`'s own edge case**: separate
    (non-united) groups are resolved sequentially against whatever's
    left of the province's defenders; if an earlier group cleanly
    sweeps them, a later group calling `fight_battle()` against an
    empty defender list will raise `ValueError`. The rulebook doesn't
    say how simultaneous separate battles against the same defenders
    are meant to interact -- not fixed here.
  - The duel *fight itself* [7.1] is still approximated, not resolved --
    the separate "Special Encounter Plan" character-combat system
    [5.10] this would need isn't built; see Phase 28's note for the
    `estimate_win_probability`-based approximation used instead.
    `tactical_ability` now reads a real skill level when the commander's
    `LeaderState.skills` is set (Phase 30), 0 otherwise.
  - ~~Contested-province state across multiple turns
    (`turn/contested_province.py`'s functions exist but nothing calls
    them from `execute_move()`/`fight_battle()`)~~ **the illegal-move
    check is wired in as of Phase 36** -- see above. Still open: a
    contested result still just sets `ProvinceState.contested_by_kingdom_id`
    and stops there, with no automatic rebattle "in the next phase"
    (needs turn-loop restructuring, see Phase 36's note above).
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
## What's excluded from this phase

- `SE3__T*.K1` files: same extension as the move files, but these are
  actually generated turn *reports* (narrative prose), not move data — kept
  as future reference output for the report-generation phase, not used here.
- `GW3__T*` files: a different, denser numeric format — not yet investigated.
