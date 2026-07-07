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
- **Phase 7 (current)**: who wins (`turn/battle_luck.py`,
  `turn/battle_resolution.py`): the two random luck events (column luck on
  front-line units, one whole-battle luck event favoring a random side)
  and `resolve_battle()`, which lines up both sides, applies luck, and
  rolls an actual winner per column and overall. Report generation is
  still a later phase.

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
- **Terrain-based battle-line-length shortening** (`turn/battle_line.py`
  `terrain_line_length_cap`) — the rulebook says terrain can shorten the
  defender's line ("see the Terrain Table") but no such numbers exist
  anywhere in the available rulebook text or Pascal source; the only
  trace (`SAY.PAS`'s `_linelen`) just formats an already-computed value
  for reports. Left as an optional externally-supplied parameter with no
  default derivation — without it, outflanking never triggers.
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

## Not yet implemented (by design, this phase)

- **Chasing a non-adjacent target** (rulebook [3.1]): moving towards a hex
  that isn't adjacent, through friendly territory, with tie-break
  priorities and a "stop chasing" condition — needs a pathfinding
  algorithm; `resolve_move()` raises `NonAdjacentMoveError` for now.
- **Actually fighting a battle** (rulebook [7.0]-[7.8]): `resolve_battle()`
  (`turn/battle_resolution.py`) now lines up both sides, applies both luck
  events, and rolls an actual winner per column and overall — but it
  still doesn't execute a battle end-to-end. Still needed:
  - **Eliminating or demoting the losing armies.** `resolve_battle()`
    decides *which side* wins each column but doesn't touch unit rosters,
    quality levels, or the "Fleets fighting on land are reduced to
    Depleted instead of eliminated" exception.
  - Race/terrain strength bonuses ([6.3] "ARMY STRENGTH NOTES": +1 for
    racial affinity with an army type, +1 for home terrain, halved in
    adverse terrain) — the stacking order with quality, defender bonus,
    and nemesis penalty isn't specified anywhere, so combining them would
    be guessing an interaction, not just a missing number.
    `BattleUnit.effective_strength` must be supplied pre-computed by the
    caller until this is resolved.
  - Tactical-ability switching itself: `switch_chance()` gives the
    probability, but nothing performs the swap between a column's front
    and rear units yet.
  - The non-humanoid "attack the rear unit instead of the front" targeting
    nuance [7.2] — `battle_line.py` models overflight units as always
    contributing 100% wherever they're placed, but doesn't model them
    choosing to target a different depth on the opposing side.
  - Supreme Commander selection and duels [7.1].
  - Pursuit [7.3], Retreat [7.4], post-battle quality-level changes
    [7.5], Contested Provinces [7.6], Conquest movement cost [7.7], and
    Multiple Contingents [7.8].
  - `resolve_move()` still only flags that a battle would be triggered
    (`battle_expected`); it doesn't call `resolve_battle()` yet.
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
