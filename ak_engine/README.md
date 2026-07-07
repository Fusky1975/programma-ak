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
- **Phase 15 (current)**: the kingdom treasury, and RECRUIT now actually
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
  existing higher-quality mercenary instead isn't modeled, no mercenary
  pool exists) with 0 movement points (a conservative default; the
  rulebook doesn't say whether a freshly recruited army can act the same
  phase). The per-type per-turn recruit limit is now enforced *across*
  multiple Recruit orders in the same province via the new
  `ProvinceState.recruited_this_turn` counter, not just within a single
  order. Requesting more of a type than the limit allows or the treasury
  can afford recruits as many as possible and reports the rest as
  blocked -- a documented choice, not a sourced rule (see
  `turn/recruit_execution.py`'s docstring).
  Every other `ActionCode` still raises `UnsupportedActionError` -- see
  "Not yet implemented" below. Report generation is still a later phase.

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
- **`plan_dispatch.py` closes the loop for 6 of 22 `ActionCode`s.** LMOVE,
  EXPLORE, LEAVE, PICK_UP, and (as of Phase 15) RECRUIT all now run
  end-to-end with real `GameState` mutation; DISBAND still only decodes.
  Every other action (Search, Hire, Fire, Cast, Use_MI, Challenge,
  Practice, ASpy, Trade, Defend, Pursue, Trail, Wait, No_Action,
  Succ_Trail, Move_Abort) raises `UnsupportedActionError`.
  - **Recruit's remaining gaps**: the "Average-or-better mercenary
    already present gets hired instead of a fresh levy" path isn't
    modeled (no mercenary pool); the recruiting leader must already
    exist as a `LeaderState` at the target province (no validation that
    a *co-located* character issued the order); and the rulebook's more
    specific "1-2 recruitable types per province" isn't tracked, only
    approximated via race-compatibility (see Phase 12's note above).
  - **Actually applying a decoded Disband request.** Releasing an army
    "into mercenary status" needs a way to represent an unowned army
    (`ArmyState.kingdom_id` isn't nullable, and there's no mercenary
    pool) -- the Phase 14 command model doesn't close this gap, since
    Disband isn't about *who leads* an army but *who owns* it.
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
- **Actually executing a Recruit order** (rulebook [3.4]): `resolve_recruit()`
  only computes the per-turn unit limit and gold cost for one army type in
  one province. Not modeled yet, and needed before this can run
  end-to-end: kingdom treasury/gold balance, a kingdom's existing army
  roster (to know if a type is already "native to province" via
  commanded armies), the mercenary pool (whether an Average-or-better
  mercenary of that type is already present, which hires them instead of
  levying from the populace), and the ally "Treat" order precondition for
  recruiting in allied territory.

## What's excluded from this phase

- `SE3__T*.K1` files: same extension as the move files, but these are
  actually generated turn *reports* (narrative prose), not move data — kept
  as future reference output for the report-generation phase, not used here.
- `GW3__T*` files: a different, denser numeric format — not yet investigated.
