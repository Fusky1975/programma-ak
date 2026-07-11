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
    unbuilt system. No dedicated template for those specific facts
    turned up anywhere in the available Pascal source (`SPDESC.X2`/
    `FPDESC.X2` looked promising by name but are Search Feature-power
    descriptions, unrelated). **Rendering the rest of `SpyReport` stays
    open** -- the same category of gap as Hide_Feature/Clairvoyance,
    not force-composed from invented prose.
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
  DISBAND (Phase 16), HIRE/FIRE (Phase 17), PRACTICE (Phase 44, always
  resolved as solo -- see that phase's note above), and (for
  Charm/Kill_Enemy only) CAST (Phase 29) run end-to-end with real
  `GameState` mutation; SEARCH (Phase 19), TRADE (Phase 20), CAST's
  other 10 spells (Phase 23/29), USE_MI (Phase 24), CHALLENGE/PURSUE
  (Phase 25), ASPY/DEFEND (Phase 26), and TRAIL (Phase 27) decode but
  don't mutate `GameState` (see their notes above -- same decode-only
  status Recruit had before Phase 15); WAIT, NO_ACTION, and MOVE_ABORT
  (Phase 22) dispatch as bare no-ops. Only **Succ_Trail** raises
  `UnsupportedActionError` -- deliberately, by design, not as an
  oversight (see Phase 27's note above).
  - **Recruit's remaining gaps**: ~~the target leader who will command a
    newly recruited army isn't validated as co-located (or even as
    existing at all) before being assigned command~~ **fixed in Phase
    47** -- see that phase's note below. Still open: the rulebook's more
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
    resolution, [5.2]-[5.8]) plus stochastic feature-content generation.
    `turn/encounter.py` (Phase 48) now provides a first slice of the
    former (Melee + Fire Arrow combat math only, not yet wired to
    Search itself -- see that phase's note below), so this gap is
    narrower than it was, not closed. A Cast/Use_MI/Give tactic's
    sub-object is also just a raw int -- no decoded spell-id or
    magic-item-id table exists in this project yet to resolve it
    further.
  - **Trade's remaining gap** (see Phase 20's note above): the whole
    module, not just execution -- `obj`/`extra`'s field meanings aren't
    confirmed, so there's nothing yet to safely execute even if a
    resolver existed. The Kingdom-level "Treat" diplomacy order
    (scientific-discovery exchange between Allies, [8.4]) is a separate,
    entirely unstarted system -- not parsed, not modeled, no real data
    available yet either.
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
    "always solo" approximation. Tactical's army-quality-training
    variant and Sage's extra device-discovery roll are separate,
    still-unmodeled special cases (see Phase 44's own note).
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
    stay unrendered, plus taxation reporting (no per-province tax-base
    model exists). `obj`
    (`target_province`) still stays an unconverted, untrusted raw int
    for both actions -- Phase 62 sidesteps needing it for ASpy at all by
    reading the rulebook's own "he is actually in" text literally
    instead. Zero real examples for either action either.
  - ~~**Trail's remaining gap** (see Phase 27's note above): decoded but
    unexecuted~~ -- **Trail's catch-up resolution is now implemented**
    (`turn/trail_execution.py`, Phase 52), reusing Phase 51's Spy Table
    directly ([4.33]'s "Chance to Pursue **or Trail**" is one shared
    column). **Still open**: the actual spied-on intelligence payload
    (Actions, race, temper, alignment, treasures, armies led) isn't
    assembled -- no report-generation system exists yet to route it to,
    and several of those fields (race, temper, alignment, per-leader
    treasures) don't exist on `LeaderState` at all, so there is nothing
    concrete to report even if there were somewhere to send it. Succ_Trail
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
    check is wired in as of Phase 36** -- see above. Still open: a
    contested result still just sets `ProvinceState.contested_by_kingdom_id`
    and stops there, with no automatic rebattle "in the next phase" --
    `turn/turn_processor.py run_turn()` (Phase 45) is now a real
    phase-by-phase, multi-leader orchestrator, but doesn't wire this
    specific mechanic in either; see that phase's note below.
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
  phase's own note above -- but actually populating a game's feature
  roster (world generation), generating rumors, and resolving a Search
  are all still entirely unbuilt, same as before. Treasures and rumors
  are still entirely unbuilt, and so is everything outside a fought
  battle: the letter-report frame, financial report, and exploration
  narrative all still need `GameState` data or a turn-events log this
  project doesn't have yet.
## What's excluded from this phase

- `SE3__T*.K1` files: same extension as the move files, but these are
  actually generated turn *reports* (narrative prose), not move data — kept
  as future reference output for the report-generation phase, not used here.
- `GW3__T*` files: a different, denser numeric format — not yet investigated.
