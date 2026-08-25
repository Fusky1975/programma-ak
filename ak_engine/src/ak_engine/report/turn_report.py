"""Battle-outcome narrative rendering (Phase 61) -- the first real consumer of
``report/prose.py``'s rendering engine (Phase 58), reusing the already-fully
modeled battle output (``BattleReport``/``BattleResult``, Phases 9/28/59/60)
to produce the same narrative sentences the original game's turn report gave
for a fought battle.

**Scope**: only the battle-outcome slice of a turn report -- the per-column
"clash" sentence, the battle-winner sentence, and destroyed/pursued/retreated
-army sentences. **Not attempted here** (see README's "Not yet implemented"):
the letter-report frame, financial report, exploration narrative, feature
discovery, or any narrative outside a fought battle -- those need `GameState`
data this project doesn't track yet (character correspondence, treasury
deltas, discovered features) or a turn-events log, a separate, much larger
follow-up. Populating a brand-new turn report end to end from a real played
turn is therefore still out of scope; this module only turns an
already-computed ``BattleReport`` into English sentences.

**Sourced from `HostAK/TP/SAY.PAS`'s `_BClash`/`_BRes`/`_BWinner`/`_BDie`/
`_BPurs` dispatch (around lines 1092-1139 of that file, inside
`Programma Pascal.zip`), and the real `HostAK/TP/PROSE/*.X` template files
it names** -- not guessed:

- ``_BClash``: ``Say('= fought/Rbattled {with }',S_Batt)`` then a second
  ``Say('=',S_Batt)`` -- the front unit of each battle column, named via
  ``=`` twice (attacker, then defender).
- ``_BRes``: immediately follows with ``Say(' and',S_Batt)`` then a
  per-column result integer (``bres``) bucketed into 11 template files --
  MINUS5..MINUS1, ZERO, PLUS1..PLUS5 -- via
  ``CASE bres OF -32000..-5: FD('minus5',...); ... 5..32000: FD('plus5',...)``.
  **Phase 370 update**: a real static disassembly of `AK.EXE`/`AK.OVR`
  (`turn/combat.py column_bres`) now gives the real, confirmed `bres`
  formula itself, not just these case boundaries -- ``turn/battle_
  resolution.py resolve_battle`` computes and stores it directly on
  ``BattleColumnResult.bres``, so this renderer reads that real value
  straight, no reconstruction needed. (The pre-Phase-370 version of this
  module derived an analogous margin from a win-probability estimate,
  documented then as an unsourced bucketing choice -- superseded now
  that the real value exists.)
- ``_BWinner``: ``FD('winner',S_Batt,3)`` on an attacker win. A defender
  win reuses ``HostAK/TP/PROSE/DEFWIN.X`` (present in the same directory,
  its content structured identically to WINNER.X -- an attacker-vs-defender
  pair of outcome templates). No template exists anywhere in the archive
  for a **tied** battle -- ``render_battle_winner`` returns ``None`` for
  ``BattleResult.winner == "tie"``, not a guessed sentence.
- ``_BDie``: ``FD('killarmy',S_Batt,4)`` per destroyed army.
- ``_BPurs``: ``FD('pursuit',S_Batt,5)`` per pursuit-destroyed army --
  ``render_pursuit_and_destroy`` reuses the same killarmy phrasing this
  module already has for ``destroyed_army_ids``, prefixed by PURSUIT.X's
  own clause, matching ``_BPurs`` immediately preceding a later ``_BDie``
  in the same dispatch table.

**Templates transcribed here use `PROSE.TXT`'s own translator-facing
notation (`^A`, `^S`, ...), the same convention `report/prose.py`'s own
tests already use -- not the compiled `.X`/`.X2` files' raw single-byte
control-character encoding.** Inspecting the actual file bytes (not just
a printed preview, which silently swallows control bytes) confirms e.g.
``RETREAT.X`` encodes ``^S`` as a literal ``\\x13`` byte and ``^A`` as
``\\x01`` -- Turbo Pascal's `chr(1)`..`chr(26)` "Ctrl+<Nth letter>"
compact story-encoding convention. Converting that compiled encoding back
to source notation is a one-time transcription step done here, not a
runtime concern ``prose.render()`` needs to solve.

``^S`` is documented in ``PROSE.TXT`` line 65 as "Province name #2" --
used by RETREAT.X for the retreat destination, distinct from ``@``
(RETREAT.X itself has no ``@`` at all, only ``^S``, matching the real
template text). ``>`` is documented at line 34 as "first character
possessive" ("My"/"His"/"Her"/"Its").

``<``/``<2``/``<3``/``[``/``[1``/``[3`` (character references, first vs.
second "person") and ``>`` (possessive) stay the caller-supplied-literal
-text values ``report/prose.py``'s own docstring already allows, since the
full narrator-perspective/pronoun system (``RUMORS.PAS Set_Person``/
``Set_Alt``) remains out of scope -- the same gap Phase 58 flagged. This
module always substitutes one literal name string for every person/tense
variant of a given side (``<`` and ``<2`` both become the same attacker
name); a true pronoun ("he"/"his troops") is never produced.

**"Army name"** (rulebook example: "the 231st Bowmen"). **Correction
(Phase 236):** a prior version of this docstring claimed no
ordinal-numbering/naming system exists anywhere in this project, citing
`LNAMES.PAS`/`PRNAMES.PAS` -- those are just leader/province first-name
word lists, not the real naming code, and the claim was simply wrong:
`models/army_naming.py make_army_name()` (`YAK.PAS Make_AName`, Phase
149) has existed since long before this correction, and was already the
project's established general-purpose per-army-naming utility (Phase
212's own `_army_display_name()`/`_trail_army_name()`). `describe_battle()`
below now uses it too, via its own `build_battle_army_names()` helper.
There's also a second, distinct, real army-naming routine as of Phase
236 (`turn/army_naming.py`, `REPORTS.PAS:986-992`'s own Army List table
builder, verified against real letter data) -- a different report
context (a tabular listing, not narrative prose) with its own real
`" Skel "` marker for Skeletal-Army-raised units. **Phase 281**: its
branch logic (not its ordinal-number prefix) is now wired into
`describe_armies_report()` below, closing the "not wired into any
function below" gap this note used to flag -- see that function's own
docstring for the full correction. Province-naming still has no real
source at all; every function below still takes caller-supplied
province display-name strings, the same values-dict pattern
``prose.render()`` itself already uses.

**Phase 63 addendum -- uncontested conquest and the Spy report's opening
line.** Two more real, standalone templates, added the same way:

- ``HostAK/TP/PROSE/CONQ.X`` narrates a Move that conquers an
  undefended enemy province (no `_BClash`/`_BWinner` battle dispatch
  involved at all -- `turn/conquest.py`'s own movement-cost rule
  already distinguishes this case from a fought battle).
  ``render_uncontested_conquest()`` doesn't call into
  `turn/move_execution.py`/`turn/conquest.py` itself; like every other
  function here, it only renders already-known facts the caller
  supplies. ~~Only 2 of CONQ.X's real 4 variants are used -- the other
  two need the "/S" (Sea-terrain) marker `report/prose.py` deliberately
  doesn't resolve, and this function takes no terrain parameter to
  resolve it with~~ -- **all 4 variants are used as of Phase 74**,
  which added `/S` resolution to `report/prose.py` and an `is_sea`
  parameter threaded through every function here whose own template
  set contains a `/S` marker (`render_column_clash`,
  `render_battle_winner`, `render_retreat`, `render_uncontested_conquest`,
  `describe_battle`); see `_CONQ_TEMPLATES`'s own comment.
- ``HostAK/TP/PROSE/SPY.X`` (``SAY.PAS _LSpy: FD('spy',S_PCom,10)``) is
  ASpy's own report-opening sentence -- closing part of Phase 62's own
  documented follow-up ("rendering a `SpyReport` into English sentences
  is a natural, still-open follow-up"). **Only the opening line renders
  here.** Research for this phase traced `RUMORS.PAS Set_Intel` (the
  procedure `turn/aspy_defend_decode.py` already cites for confirming
  `obj` is engine-consulted) and confirmed it computes cross-kingdom
  *report-visibility* levels (`intel_lev`, gating what *other* kings
  learn about a spying event in their own reports) -- a separate,
  unbuilt system, and not what actually composes the "owner / adjacent
  owners / recruitable types / capital" sentences themselves. ~~No
  dedicated PROSE template for those specific facts turned up anywhere
  in the available Pascal source~~ -- found in Phase 115 below, sitting
  in `SAY.PAS` immediately after `_LSpy`'s own dispatch in the very same
  procedure (`SPDESC.X2`/`FPDESC.X2` really are unrelated Search
  Feature-power descriptions, despite the similar name -- that part of
  the original note still holds). Rendering the rest of
  `turn/aspy_execution.py SpyReport` is mostly closed as of Phase 115 --
  see its own addendum for the two facts (`_LSLeads`/`_LSGarr`) still
  genuinely blocked on an unbuilt capability, the same category of gap
  as Hide_Feature/Clairvoyance.
- ``SPY.X``'s own ``^B``/``^E`` markers are Turbo Pascal's
  King-exclusion narrator markers (`RUMORS.PAS Set_Person`/`Set_Alt`,
  already flagged out of scope by `report/prose.py`'s own docstring);
  `render_spy_report_opening()` elides both (substitutes empty string)
  rather than guessing what text a full narrator-perspective system
  would put there.

**Phase 96 addendum -- Search discovering a Magic Feature.**
``HostAK/TP/PROSE/MAGFEAT.X2``, found continuing to mine the ``PROSE/``
``.X2`` template files directly (rather than just the Pascal source that
names them), the same way Phases 91/92/95 found real data outside
``CTBOTH.PAS``.

- The file's header (``"20 1"``) parses via this module's own
  ``parse_template_choices`` convention as 20 choices, 1 line per choice
  -- but the file has 21 real content lines. Line 1 is the "no magic
  feature found" sentence (``MagicFeature.NONE``); lines 2-20 are 19
  *textually identical* "found a magic item" filler sentences
  (positionally corresponding to ``MagicFeature`` ordinals 1-19,
  ``POOL``-``SEALED_ENTRANCE``, but the sentence text never actually
  varies by which one); together that's exactly the header's declared
  20-line choice pool. Line 21, outside that pool, is a distinguished
  sentence for ``MagicFeature.ITSELF`` (ordinal 20) -- not chosen by the
  same random-pick mechanism the header describes, matched here by
  selecting on ``magic_feature`` directly rather than via
  ``pick_variant``.
- ``render_magic_feature_discovery()`` substitutes ``models/
  magic_feature.py MAGIC_FEATURE_NAME``'s own raw string straight into
  the template's ``$\\`` marker, unresolved -- `MAGIC_FEATURE_NAME`'s own
  docstring already documents these strings as raw, unresolved `/F`/`/S`
  compound templates (Phase 92). They can't be resolved by routing back
  through `report/prose.py render()`'s own `/F`/`/S` support either:
  `render()`'s pipeline resolves choice markers **before** substituting
  placeholder values (see `report/prose.py`'s own docstring), so a
  marker arriving *inside* a substituted value is never revisited. A
  sentence rendered by this function therefore still shows the raw
  ``"Pool/FStream"``-style text at the substitution point -- a known,
  already-documented limitation carried forward, not silently
  mis-resolved.

**Phase 104 addendum -- the Move action's own report line.**
``HostAK/TP/PROSE/MARCH.X`` (header ``"3 1"``), confirmed real via
``SAY.PAS``'s own ``_LMarch`` dispatch: ``FD('march',S_Admin,3)``. The
``dex`` parameter (``3``, matching the file's own 3 declared choices) is
small enough to fall into ``RUMORS.PAS FD``'s per-character-seed
pseudo-random selection scheme, not the deterministic ``1001+X``
indexing every earlier `.X2`-sourced phase in this module used --
confirmed by reading ``FD``'s own body (``RUMORS.PAS`` ~line 2288-2333):
``dex < 100`` routes through ``fdcode``/``fdinc``/``Good_Inc``, the same
unrecoverable "story-code bytecode log" `pick_variant()`'s own docstring
already flagged for ``CONQ.X``/``SPY.X`` (Phase 63). `render_march()`
therefore uses the same `parse_template_choices`/`pick_variant`
infrastructure those two already established, not a new indexing scheme.

The raw ``\\x10`` control byte in ``MARCH.X``'s own text is `PROSE.TXT`'s
``^P`` marker ("Province number", e.g. `"0304"`) -- transcribed in
source notation per this module's own established convention (see the
``^S`` note above).

**More real, confirmed `.X`/`.X2` findings surfaced but deliberately
deferred**, each needing more design work than this phase's scope:
``RWENC.X`` (a "random encounter while traveling" narrative, `_LWEnc`) --
fixed in Phase 106. ~~`TACTICS.X2` (a 9-level tactical-superiority
bucket, structurally analogous to this module's own `margin_bucket()`,
but `battac`'s own formula isn't traced)~~ -- fixed in Phase 109 below
(`battac`'s own formula is still untraced, but the bucket *scale* itself
is now reproduced the same documented, unsourced way `margin_bucket()`
already was). ``NEMESIS.X2`` (`_ANem: FD('...nemesis.x2',S_Batt,
1000+Rint)` -- real and dispatched, but `Rint`'s own value isn't a
formula this project can trace, and the file's own content mixes
recognizable `ArmyType` nemesis pairs with unmodeled monster types like
"Dinosaurs") -- raw content added in Phase 109 below, still with no
render function or index-to-`ArmyType` mapping asserted.

**Phase 109 addendum -- TACTICS.X2 and NEMESIS.X2.** Both confirmed
real via `SAY.PAS`'s own `_BTac`/`_ANem` dispatch (~lines 1058-1064 and
1084), both immediate siblings of `_BLuck`/`_CLuck` in the very same
`Imp_Code` block already read for `_BRes`/`margin_bucket()`.

- ``TACTICS.X2`` (header ``"9 1"``, exactly 9 real lines, matching the
  file's own declared count) forms a **confirmed, monotonic 9-point
  spectrum** once read end to end: template 1 ("[''s tactical strokes
  of genius doubled ]'s strength") is total advantage for the *defender*
  (`[`), template 5 ("neither leader could gain a tactical advantage")
  is dead even, template 9 ("tactical supremacy... by <'s unmatched...
  genius") is total advantage for the *attacker* (`<`) -- and the
  `_BTac` dispatch's own `battac < 5`/`battac > 5` comparisons confirm 5
  is the intended midpoint. `tactical_margin_bucket()` reuses this
  confirmed scale, fed by `turn/battle_line.py`'s own real
  `attacker_tactical_ability`/`defender_tactical_ability` (rulebook
  [7.2]) -- the same "documented, unsourced bucketing choice" precedent
  `margin_bucket()` already established for `bres`, not a recovered
  formula for `battac` itself.
  **Phase 370 note**: `margin_bucket()` itself no longer exists -- a real
  disassembly gave the true `bres` formula directly (`turn/combat.py
  column_bres`), so `render_column_clash` now reads `BattleColumnResult.
  bres` straight instead of reconstructing it. `tactical_margin_bucket()`
  is unaffected (`battac`'s own formula is still untraced) and keeps its
  own "documented, unsourced bucketing choice" status on its own merits,
  no longer by analogy to a sibling function that's since become real.
- ``NEMESIS.X2`` (header ``"100 1"``, only 15 of the declared 100
  choices populated) is modeled more conservatively: `NEMESIS_TEMPLATE`
  stores all 15 real lines verbatim, keyed by their own raw file
  position (1-15), with **no** `ArmyType`-keyed lookup or `render_*`
  wrapper. Cross-checking against `models/army_type.py`'s own rulebook
  -sourced `NEMESIS` dict finds unmistakable content matches for 7 of
  the 15 lines (e.g. line 3's "unwieldy formation... tested by the
  flexible Legionnaires" is `Phalanx`'s real `Legion` nemesis; line 7's
  "and their mounts... the dreaded... screaming Eagles" is `Warg
  Riders`' real `Eagle Wing` nemesis; line 10's "picked off... by
  Mermen... barbed harpoons" is `Whales`' real `Mermen` nemesis) --
  strong supporting evidence this is the genuine Nemesis-in-battle
  narrative, not a coincidence. But 3 of the modeled `ArmyType` nemesis
  pairs (`Dragon Wing`/`Eagle Wing`/`Mermen`, all -> `Bowmen`) share
  exactly 3 candidate lines (8, 9, 11) with no further textual
  distinction confirming which line belongs to which attacker, and
  lines 2 and 15 both name unmodeled "Dinosaurs"/"Sauropods" -- so no
  index scheme is asserted, per this project's sourcing discipline.

**Phase 105 addendum -- Steal/Flee maneuver failure.**
``HostAK/TP/PROSE/FLEEFAIL.X`` and ``SNEAKUP.X``, both confirmed real,
found finishing the Phase 104 investigation.

- ``FLEEFAIL.X`` (header ``"4 1"``) is dispatched via `SAY.PAS`'s own
  `_LCot: FD2('fleefail',S_PCom,3)`. `FD2` is a thin wrapper
  (`FD2(fn,spl,dex) = FD(fn,spl,dex+5*ord(_attl<>bestldr))`) that still
  routes through `FD`'s own `dex < 100` per-character pseudo-random
  scheme (see the Phase 104 addendum above) regardless of the `+5`
  offset -- both `dex=3` and `dex=8` are independent pseudo-random state
  slots picking among the *same* 4 real template lines, not a wider
  choice pool. `render_flee_failure()` therefore uses `pick_variant()`
  exactly like `render_march()` does. Every template here is a complete,
  self-contained sentence -- unlike `SNEAKUP.X` below, no trailing
  completion clause is needed.
- ``SNEAKUP.X`` (header ``"4 1"``) is dispatched via `_LSeen`:
  `FD('sneakup',S_PCom,7)`, immediately followed by a **separate** story
  -code read (`Rint`, not the same value driving the `FD` call itself)
  selecting one of three literal completion clauses: `CASE Rint OF 0:
  Say(' melee range.',S_PCom); 1: Say(' bow range.',S_PCom); 2:
  Say(' spell range.',S_PCom); END;`. Every one of `SNEAKUP.X`'s own 4
  templates ends mid-sentence with the word "at", confirming they're
  meant to be immediately followed by one of these three clauses.
  `render_sneak_detected()` takes the completed clause as an explicit
  parameter (`range_suffix`) rather than guessing which of the three
  applies -- this project has no source for what decides melee/bow/spell
  range, the same category of caller-supplied fact as `is_sea`. The
  three confirmed clauses are exported as
  `SNEAKUP_RANGE_MELEE`/`SNEAKUP_RANGE_BOW`/`SNEAKUP_RANGE_SPELL` for
  callers to pick from, rather than inventing a new enum with no Pascal
  source of its own (`Rint`'s own 0/1/2 values are a bare `CASE`, not a
  named type anywhere in the available source).

**Phase 106 addendum -- a wandering encounter's opening sentence.**
``HostAK/TP/PROSE/RWENC.X`` (header ``"4 1"``), confirmed real via
`SAY.PAS`'s own `_LWEnc` dispatch: `BEGIN randlevel:= 1;
FD('rwenc',S_Adv,3); END;` -- the opening/intro sentence for stumbling
into a wandering encounter while traveling, distinct from Search's own
`models/intro.py Intro` (Phase 99, which is specifically about
discovering a geographic `Feature`, not a chance meeting on the road).
`dex=3` again falls into `FD`'s own `dex < 100` pseudo-random scheme
(Phase 104's own finding), so `render_wandering_encounter()` reuses
`pick_variant()` the same way `render_march()`/`render_flee_failure()`
do.

**A larger, real "wandering/patrol encounter outcome" system was found
alongside it, deliberately left out of scope**: `SAY.PAS`'s own
`_LPass`/`_LBefr`/`_LTricks`/`_LDense`/`_LDona`/`_LHear`/`_LNice`/
`_LGreet` are plain, non-`.X`-sourced `Say(...)` calls describing what
happens *after* the RWENC.X opening (declining to fight, exchanging
tips, hearing rumors of a Feature, sharing a drink, ...), and
`_LEnc`/`_LSafe`/`_LPEnc` dispatch their own sibling `.X` files
(`enco.x`, `safpat.x`, `patenc.x`) for closely related encounter
variants (`_LPEnc` sets `randlevel:= 2` instead of RWENC's `1`,
suggesting a distinct danger-level tier). Modeling that whole outcome
tree is a real, standalone follow-up phase, not attempted here.

**Phase 107 addendum -- the three sibling `.X` files themselves.**
`ENCO.X`, `SAFPAT.X` and `PATENC.X`, all confirmed real via `SAY.PAS`'s
own dispatch:

- `ENCO.X` (header `"1 1"`) is `_LEnc: FD('enco',S_Adv,1)` -- the
  simplest possible encounter opening, a single template.
- `SAFPAT.X` (header `"3 1"`) is `_LSafe: FD('safpat',S_Adv,1)` --
  getting caught but then released (a convincing official seal, an
  impressed judge, not actually being on a wanted list).
- `PATENC.X` (header `"4 1"`) is `_LPEnc: BEGIN FD('patenc',S_Adv,4);
  randlevel:= 2; END;` -- a more dangerous patrol/bounty-hunter
  encounter (beaten and tracked down, challenged as a suspected spy,
  killed a rogue in a duel only for his kin to come seeking revenge).

All three `dex` values are small enough to fall into `FD`'s own
`dex < 100` pseudo-random scheme (Phase 104's own finding), so every
render function here reuses `pick_variant()`. The raw `\\x0b` control
byte both `SAFPAT.X` and `PATENC.X` carry is `PROSE.TXT`'s own `^K`
marker ("King name and title", e.g. "King Harold the Bold") --
transcribed in source notation per this module's established convention.

**Phase 110 addendum -- the Explore action's own report family.** Found
scanning the wide `_LDies`..`_LTreas` (3000-3063) stretch of
`RUMORS.PAS`'s story-code `CONST` block for the first time -- this
module had so far only mined the 3300+ "encounter table" stretch. Ties
directly to `turn/exploration.py resolve_explore()` (Phase 3) and
`turn/move_execution.py`'s own partial-exploration side effect (also
Phase 3), the first time a `.X`-sourced narrative in this module pairs
with an already-modeled, already-numeric game mechanic (`ExploreResult
.new_percent`) rather than being purely decorative.

- `_LExpImp: FD('expmove',S_Adv,0)` -> `EXPMOVE.X` (header `"6 1"`, 6
  real templates) is the Explore action's own progress report,
  dispatched for a dedicated Explore. `render_explore_progress()`.
- `_LExpCo: FD('coexp',S_Red,1)` -> `COEXP.X` (header `"6 1"`, 6 real
  templates) is the same progress report but phrased as exploration
  gained *while marching* -- matching `_LMove`'s own sibling `_LExpCo`
  dispatch in `SAY.PAS` (~line 441, immediately after `_LExpDiff`) and
  `move_execution.py`'s own already-modeled "Move's partial-exploration
  side effect". `render_explore_continued()`.
- `_LExpMax`: a single, real, hardcoded `Say(...)` (no file) for
  "already fully explored" -- `EXPLORE_ALREADY_MAXED_TEMPLATE`,
  `render_explore_already_maxed()`. Maps to `ExploreResult
  .fully_explored` being already `True` before this Explore ran.
- `_LExpDiff`: a single, real, hardcoded precursor clause ("< wasn't in
  @ so ", no trailing period) that `SAY.PAS` prefixes onto one of the
  three codes above when the exploring character wasn't actually
  located in the target province -- `EXPLORE_NOT_PRESENT_PREFIX`, a
  bare string constant (the caller concatenates it, the same "raw
  template, no wrapper" choice `POWER_CONDITION_REJECTION_INTRO`
  established in Phase 101).
- `_LExpFail`: confirmed real in the `CASE` (`SAY.PAS` line 453) but is
  a literal empty statement (`;`) -- produces no text at all. Documented
  here, not modeled as a function, since there is nothing to render.
- `_LExpAtt` (3002) is declared in `RUMORS.PAS`'s own `CONST` block but
  has **no** dispatch anywhere in `SAY.PAS` -- an orphaned constant,
  not pursued (no confirmed content to model).

Both `EXPMOVE.X` and `COEXP.X` carry the `^B`/`^E` King-exclusion span
around their own "...% has been explored" clause (`PROSE.TXT`'s
"excluded from the General Intelligence Reports of other players") --
the same already-documented, deferred marker `models/local_encounter.py
HEAR_OF_FEATURE` used in Phase 108, transcribed verbatim here too.
`dex` is `0`/`1` for the two files respectively -- both `< 100`, so
both render functions use `pick_variant()` per the established `FD`
litmus test, not deterministic indexing.

**Phase 111 addendum -- the Fire Arrow attack sequence.** Continuing
the 3000-3099 stretch of `RUMORS.PAS`'s story-code `CONST` block: the
personal-combat narrative for closing to range and firing, ties
directly to `turn/encounter.py`'s already-modeled Fire Arrow combat
(`roll_fire_arrow_attack()`, Phase 48) the same way Phase 110 tied
Explore's own narrative to `resolve_explore()`.

- `_LToBow: FD2('gobow',S_PCom,2)` -> `GOBOW.X` (header `"3 1"`, 3 real
  templates): closing to bow range. `render_move_to_bow_range()`.
- `_LToMel: FD2('gomel',S_PCom,3)` -> `GOMEL.X` (header `"3 1"`, 3 real
  templates): closing to melee range, requested alongside the above for
  symmetry even though this phase only wires the Fire Arrow side of
  combat -- `render_move_to_melee_range()`. Its own attack-action
  sibling (`_LSwing: FD2('swangat',S_PCom,3)` -> `SWANGAT.X`, 11
  templates, confirmed real while researching this phase) is left for a
  Melee-combat follow-up phase, not modeled here.
- `_LFArr: FD2('farr',S_PCom,4)` -> `FARR.X` (header `"6 1"`, 6 real
  templates): the Fire Arrow attack action itself. Carries `\\x01` (`^A`,
  article) and `\\x17` (`^W`, `PROSE.TXT`'s "Striking weapon" marker,
  e.g. "arrow") alongside `$S` (`PROSE.TXT`'s "Attack method" marker,
  e.g. "Fired") -- `render_fire_arrow_attack()` hardcodes `$S`="Fired"/
  `^W`="arrow" since this file is unambiguously always about firing an
  arrow, not a situational choice. Every template ends without
  punctuation, mid-sentence -- meant to be immediately followed by a
  hit/miss continuation clause (see below), the same "no trailing
  punctuation, caller concatenates" shape `_BClash`/`_BRes` already
  established (module docstring, top).
- `_LMisses: FD2('andmiss',S_PCom,5)` -> `ANDMISS.X` (header `"5 1"`, 5
  real templates): the miss continuation clause, each starting with a
  leading space and no capital letter, confirming the concatenation
  shape above. `render_attack_missed()` takes `weapon` as an explicit
  parameter (not hardcoded) since `ANDMISS.X` is shared by both
  `_LFArr` and `_LSwing` (`^W` appears referring back to whichever
  weapon the preceding attack-action sentence named) -- a future
  Melee-combat phase can reuse it unchanged.
- `_LInfl`/`_LDevast`/`_LMortB` (the hit/overkill/mortal-wound
  continuations, real and dispatched immediately alongside `_LMisses`
  in the same `SAY.PAS` block) are confirmed real but deliberately not
  modeled this phase -- the user's own request scoped this phase to
  `_LToBow`/`_LToMel`/`_LFArr`/`_LMisses` only.

**Phase 112 addendum -- the hit/devastate/mortal-wound continuations.**
Closes the gap Phase 111 deliberately left open, completing the
Fire Arrow attack sequence.

- `_LInfl: FD2('andinfl',S_PCom,1)` -> `ANDINFL.X` (header `"5 1"`, 5
  real templates): the hit continuation clause, parallel in shape to
  `_LMisses`/`ANDMISS.X` (leading space, no capital, ends the sentence
  `_LFArr`/a future `_LSwing` started). Carries `#` (`PROSE.TXT`'s "A
  number" marker) for the damage dealt -- `render_attack_hit()` takes
  ``damage_points`` directly from `turn/encounter.py roll_fire_arrow_
  attack()`'s own already-modeled return value.
- `_LDevast: Say(' and devastated/Rannihilated [.',S_PCom)` -- a
  single, real, hardcoded template (no file), textually an obvious
  parallel to `_LInfl` (same " and..." shape, references `[`) and
  listed immediately next to it in `SAY.PAS`'s own `CASE` block.
  **Worth flagging honestly**: `RUMORS.PAS`'s own `CONST` declares
  `_LInfl`/`_LMortB` at 3018/3019 but `_LDevast` at 3160 (~line 105),
  in the unrelated King-meeting/messaging stretch (`_LSay`/`_LKMeet`
  neighbors) -- Pascal `CASE` branches don't need to be listed in
  constant-declaration order, so this doesn't contradict `_LDevast`
  being real, dispatched, combat-flavored content, but it does mean
  this project can't fully confirm it shares `_LInfl`'s own combat
  -sequence call site. Modeled as `render_attack_devastating_hit()`
  regardless (real, confirmed content), with this discrepancy
  documented rather than silently smoothed over. This project has no
  source for what distinguishes an `_LInfl` hit from an `_LDevast` one
  -- the caller decides which to render (e.g. an overkill/lethal-blow
  fact it already has), the same caller-supplied-fact pattern
  `SNEAKUP_RANGE_MELEE`/`BOW`/`SPELL` established (Phase 105).
- `_LMortB: FD2('mortwoun',S_PCom,5)` -> `MORTWOUN.X` (header `"4 1"`,
  4 real templates): a **standalone** sentence (capitalized `[1`,
  complete on its own) marking the defender's fate, appended *after*
  the attack+hit sentence rather than concatenated onto it -- unlike
  `_LInfl`/`_LDevast`/`_LMisses`, which all continue the same sentence
  `_LFArr` started. Its own 4th template ("staggered..., stunned by...
  the deadly blow") describes a stun, not a fatal wound, despite the
  file's own name -- transcribed verbatim, not smoothed into implying
  every variant means death.

**Phase 113 addendum -- SWANGAT.X, the Melee attack action.**
`_LSwing: FD2('swangat',S_PCom,3)` -> `SWANGAT.X` (header `"11 1"`, 11
real templates) -- confirmed real while researching Phase 111 and
deliberately deferred there; the Melee sibling to `_LFArr`/`FARR.X`
(same "no trailing punctuation, caller concatenates" shape, meant to
be immediately followed by `render_attack_missed()`/`render_attack_
hit()`/`render_attack_devastating_hit()`, all already generic across
attack types).

- Uses `$S` (`PROSE.TXT`'s "Attack method" marker) but, unlike
  `FARR.X`, **not** `^W` (weapon) -- `render_melee_attack()` takes
  `attack_method` as an explicit caller-supplied parameter (e.g.
  `"Slashed"`, `"Thrust"`, matching `PROSE.TXT`'s own documented
  examples for `$S`) rather than hardcoding one value, since a Melee
  weapon/verb genuinely varies by character, unlike Fire Arrow's fixed
  "Fired". 1 of the 11 templates (the first) uses a literal
  `assailed/Rattacked` verb choice instead of `$S` at all -- `$S` is
  simply unused for that variant, not a special case to handle.
- Templates 4 and 9 have real, slightly unusual phrasing worth noting
  rather than "fixing": template 4 never names the opponent via `[` at
  all, instead calling them "> {fearsome/vaunted }enemy/nemesis" (the
  attacker's own possessive + a generic descriptor); template 9 writes
  `['s defenses/Rprotection` -- `[` immediately followed by a literal
  `'s` in the source text itself (not `PROSE.TXT`'s own `]` possessive
  marker), so substituting `[` alone produces the correct
  "Borin's defenses" without any special-casing.
- No `/S` marker anywhere in this file (unlike `GOMEL.X`'s own
  movement-to-melee-range templates, Phase 111, which do carry one) --
  `render_melee_attack()` takes no `is_sea` parameter.
- The raw `\\x1a` byte at the very end of the file's last line is DOS's
  own end-of-file marker (Ctrl-Z), not narrative content -- stripped
  during transcription, not preserved as if it were part of the prose.

**Phase 114 addendum -- the Hire/Fire narrative.** `SAY.PAS` ~lines
501-504, ties to `turn/hire_fire_decode.py`'s already-modeled
`HireRequest`/`FireRequest` (Phase 17).

- `_LHire: FD('acchire',S_Adv,6)` -> `ACCHIRE.X` (header `"1 1"`, 1 real
  template): a successful Hire. `render_hire_accepted()`.
- `_LHFail: FD('refhire',S_Adv,5)` -> `REFHIRE.X` (header `"3 1"`, 3
  real templates): a refused Hire, each citing alignment
  enmity/disdain for the hiring King as the reason. `render_hire_
  refused()`. Template 3's own raw text has a real, slightly odd
  authoring quirk kept verbatim rather than "fixed": `for "Holding/R
  "Keeping ^A palace court...` -- the `/R` choice's right branch
  embeds its own literal opening quote mark alongside the word
  "Keeping", not just the word itself.
- `_LFire: FD('fireman',S_Adv,7)` -> `FIREMAN.X` (header `"4 1"`, 4
  real templates): a Fire. `render_fire_hireling()`.
- `_LCounter: Say(...)` (immediately between `_LHFail` and `_LHire` in
  `SAY.PAS`'s own `CASE` block) -- a single, real, hardcoded template
  (no file) for a *different* Hire failure reason: a price rejection
  rather than an alignment one. `HIRE_COUNTER_OFFER_TEMPLATE`,
  `render_hire_counter_offer()`.

All four carry `\\x0b` (`^K`, "King name and title") -- hiring/firing is
always narrated in service of a King. `render_hire_accepted()`'s own
single template still goes through `pick_variant()` for consistency
with every other `.X`-sourced renderer in this module (`ENCO.X`, Phase
107, established the same "1-template file still uses pick_variant"
convention).

**Phase 115 addendum -- the ASpy report body.** `SAY.PAS` ~lines
522-545, immediately after `_LSpy`'s own dispatch (Phase 63) in the
same `Imp_Code` procedure -- closes the gap that phase's own docstring
said didn't turn up anywhere (see the strikethrough above). Every code
here is a single, real, hardcoded `Say(...)` (no `.X` file), the report
-body line items `_LSpy`/`SPY.X`'s opening sentence introduces.

- `_LSTax`: `"Approximate Taxation: #"` -- `render_spy_tax_estimate()`.
- `_LSAT`: `"Province Army Type #: |"` -- `#` reads most naturally as a
  1-based index enumerating one of the province's possibly-multiple
  recruitable Army Types (`turn/recruit.py`'s own rulebook precedent
  for provinces supporting more than one type), `|` is `PROSE.TXT`'s
  own "Army type name" marker. `render_spy_army_type()`.
- `_LSList`: `"the following elements are present in @:  "` (real
  trailing double space, kept verbatim) -- the intro line for the
  detail lines that follow (`_LSHere`/`_LSLeads`/`_LSGarr`/etc.).
  `render_spy_elements_intro()`.
- `_LSHere`: `"[ $ is here."` -- carries a bare `$` with **no
  `PROSE.TXT`-documented meaning** (every real `$`-prefixed marker is
  2 characters, e.g. `$O`/`$K`/`$R`; a lone `$` matches none of them).
  Flagged honestly rather than guessed at (e.g. assumed to mean `$O`,
  Office name) -- `render_spy_character_here()` exposes it as an
  explicit `title` parameter defaulting to `""`, the same "caller may
  supply literal text for an unresolved symbol" allowance
  `report/prose.py`'s own docstring already established for `^B`/`^E`.
- `_LSNone`/`_LSNoCh`: `"there were no conspicuous characters or forces
  in @."` / `"there were no conspicuous characters in @."` -- two
  distinct negative-result lines (with vs. without forces mentioned).
  `render_spy_no_characters_or_forces()`/`render_spy_no_characters()`.
- `_LSCap`: `"@ is the kingdom's capital province."` --
  `render_spy_capital_province()`.
- `_LSEtc`: the report's own closing line, pointing further detail to
  the General Intelligence Report. `render_spy_report_closing()`.
- `_LSLeads`/`_LSGarr`: `"[ leads approximately ^L^V."` / `"there is a
  garrison of approximately ^L^V."` -- both real. ~~Both genuinely
  blocked: `\\x0c\\x16` is `^L^V`, `PROSE.TXT`'s own list-insertion
  marker applied to a list of Army names, and `report/prose.py`'s own
  docstring already defers `^L`. Exposed as raw string constants only,
  no `render_*` wrapper.~~ Unblocked in Phase 118 (`render_spy_leads()`/
  `render_spy_garrison()`) once `report/prose.py` gained its own `^L`
  list-insertion capability.

**Phase 116 addendum -- the Ally/Treat narrative.** `SAY.PAS` ~lines
506-511, immediately after `_LFire` in the same `Imp_Code` block.

- `_LAlly: FD('ally',S_Admin,8)` -> `ALLY.X` (header `"2 1"`, 2 real
  templates): a successful Ally proposal. `render_ally_proposed()`.
  Both `[3` and `[` refer to the same target King within a single
  template (e.g. template 1 addresses `[3` in "urged `[3` to improve
  relations..." then names `[` again in "...accepted by `[`") -- both
  substituted with the same `king_name` value, not two different
  characters.
- `_LATreat: Say('< treated with > ally [3.',S_Admin)` -- a single,
  real, hardcoded template (no file) for an *already-allied* notice
  (a repeat-turn "we already have a treaty" line, distinct from the
  first-time proposal `_LAlly` narrates). `render_already_allied()`.
- `_LRefA` -- a single, real, hardcoded entry made of **two separate
  `Say(...)` calls** (no file) for a refused Ally proposal.
  `render_ally_refused()` concatenates both rendered sentences with no
  separator, matching every other multi-sentence entry already found
  in this module's own templates (e.g. `PATENC.X`'s own sentences
  directly abutting with no inserted space, Phase 107) -- Turbo
  Pascal's own `Say()` just writes sequentially to the same report
  position, adding nothing of its own between calls.

**Phase 117 addendum -- Treasure/Steal narrative.** `SAY.PAS` ~lines
562-575 and 712, requested as `_LSteal`/`_LTakeG`/`_LInher`/`_LWill`.

- `_LSteal` (3037, `RUMORS.PAS` ~line 72) is declared but **has no
  dispatch anywhere in `SAY.PAS`** -- an orphaned constant, the same
  category as `_LExpAtt` (Phase 110). Only its `T_`/`G_`-prefixed
  siblings (`T_LSteal`/`T_MSteal`/`G_LSteal`/`G_MSteal`, a larger
  Steal-outcome cluster around lines 558-580 whose `T_`/`G_` prefix
  semantics aren't confirmed by any comment in the available source)
  are actually dispatched -- not pursued here, left for a future phase
  once that prefix distinction can be sourced rather than guessed.
- `_LTakeG: FD('takeg',S_PCom,2)` -> `TAKEG.X` (header `"3 1"`, 3 real
  templates): a successful gold theft. `render_take_gold()`.
- `_LInher` has a real `IF _attl = _defl THEN ... ELSE ...` branch:
  the `THEN` branch is `'The heir of < inherited/gained the ^L\\.'` --
  ~~genuinely blocked on `^L` (list of magic items). The `ELSE` branch
  ... `render_inherit()` renders only this confirmed branch.~~ The
  `THEN` branch is unblocked in Phase 118 (`render_inherit_as_heir()`);
  `render_inherit()` still renders only the `ELSE` branch (a single
  magic item, not a list -- the two branches narrate genuinely
  different situations, kept as two functions).
- `_LWill`: `"['s will left {all }] {worldly }possessions to ]
  compatriots/fellow_adventurers."` -- a single, real, hardcoded
  template (no file), the deceased's will being read.
  `render_will()`. The Pascal-escaped `''` (a literal apostrophe) after
  `[` is the same convention `REFHIRE.X`'s own transcription already
  established (Phase 114).
- `_MGain: Say('< took the ^L\\.',S_PCom)` -- a single, real, hardcoded
  template (no file), real and dispatched immediately alongside
  `_LInher`/`_LWill`. Also blocked on `^L` at the time, also unblocked
  in Phase 118 (`render_take_items()`).

**Phase 118 addendum -- ^L list insertion unblocks 3 templates.**
`report/prose.py` gained its own `^L` list-insertion capability this
phase (see its module docstring) -- ``render_spy_leads()``/
``render_spy_garrison()`` (Phase 115's own `_LSLeads`/`_LSGarr`) and
``render_inherit_as_heir()``/``render_take_items()`` (Phase 117's own
`_LInher` `THEN` branch and `_MGain`) are the first real consumers,
each simply passing its own list of item/army names through `render()`'s
new `lists` parameter -- no new template content, no new sourcing,
just closing gaps this project had already found and documented twice.

**Phase 119 addendum -- funeral pyre and failed-Steal ransom.** Two
more real, hardcoded templates (no file) found alongside `_LInher`/
`_LTakeG` while researching Phase 117, deliberately left unmodeled
there.

- `_LBurn: Say('] possessions were burned with [3 on the funeral
  pyre.',S_Priv)` (`RUMORS.PAS` `_LBurn = 3013`, immediately before
  `_LInher = 3014`) -- the deceased's own possessive (`]`) and a second
  character present at the pyre (`[3`, the same marker `ALLY.X`'s own
  target-King reference used, Phase 116). `render_funeral_pyre()`.
- `_LRans` (`RUMORS.PAS` `_LRans = 3039`, immediately after
  `_LTakeG = 3038`) -- a real entry made of **two separate `Say(...)`
  calls** (no file), narrating a failed Steal attempt: caught
  red-handed, then ransomed for half the thief's own treasury.
  `render_steal_caught_and_ransomed()` concatenates both rendered
  sentences with no separator, the same shape `render_ally_refused()`
  (Phase 116) already established for a two-`Say()` entry. `[`/`[1`
  both refer to the character who caught the thief, `<`/`<2` both
  refer to the thief -- the same "one value, two marker spellings for
  the same person" shape `render_fire_hireling()`'s own `[`/`[1`
  (Phase 114) already established.

**Phase 120 addendum -- Move/Pursue/Practice narrative.** Four more
real, single, hardcoded templates (no file), each tying directly to
an already-modeled `turn/*.py` mechanic rather than being purely
decorative -- the same "narrative for existing mechanics" pattern
Phase 110 (Explore) and Phase 111 (Fire Arrow) established.

- `_LCMarch: BEGIN Start_BI; Say('< marched into @ from ^S to defend @
  against its would-be conquerors.',S_Army); End_BI; END`
  (`RUMORS.PAS` `_LCMarch = 3111`) -- a defensive Move (reinforcing a
  province under threat), distinct from `_LMarch`/`MARCH.X`'s own
  regular Move narrative (Phase 104). `^S` (Province name #2) is the
  origin province. `render_defensive_march()`.
- `_LCatch: Say('< caught up with [ in @.',S_Adv)` -- the Pursue/Trail
  catch-up moment itself, ties to `turn/pursue_execution.py`/
  `turn/trail_execution.py` (Phase 51/52/66/68). `render_caught_up()`.
- `_LTeach: Say('< was tutored/Rinstructed in{ the art of} ^ by
  [.',S_Priv)` -- successful Practice tutoring, `^` is `PROSE.TXT`'s
  own "Ability name" marker, ties to `turn/practice_execution.py`
  (Phase 44/46). `render_practice_tutored()`.
- `_LAlrMax: Say('< practiced ^ even though < had already reached the
  maximum skill level.',S_Red)` -- immediately follows `_LTeach` in
  `RUMORS.PAS`'s own `CONST` block, narrates `turn/practice_execution
  .py`'s own already-modeled max-skill-level rule.
  `render_practice_already_maxed()`.

**Phase 121 addendum -- duel demoralization narrative.** `_ADishK`/
`_ADishF` (`RUMORS.PAS` `_ADishK = 3101`/`_ADishF = 3102`, sitting
between `_LBenc = 3100` and `_LAssume = 3103`), both real entries made
of **two separate `Say(...)` calls** (no file), narrating rulebook
[7.1]'s "if the Supreme Commander is beaten... the losing side's
forces... will become demoralized and... reduced in strength by 25%"
-- the exact rule `turn/duel.py apply_duel_demoralization()` already
models. Two narrative framings of the same mechanical event (the
Supreme Commander's own defeat in the duel), not two different rules:

- `_ADishK` -- the commander **died**: `"The forces commanded by [3
  were disheartened by ] death/Rdemise, but/Ryet still they pressed/
  Rmoved forward/Rahead with some hope of victory."`
  `render_commander_died_demoralized()`.
- `_ADishF` -- the commander was **cowardly/fled**: `"The forces
  commanded by <3 were disappointed/Rdismayed by > cowardice/
  Rfaint-heartedness.They {grimly/Rsteadfastly }marched on, though
  with lessened/Rshaken confidence."` `render_commander_fled_
  demoralized()`.

This project has no source for which of the two narrations a given
duel loss picks -- the caller decides, the same caller-supplied-fact
pattern established throughout (`is_sea`, `range_suffix`, `weapon`).
Both concatenate their two rendered sentences with no separator,
matching every other multi-`Say()` entry already found in this module
(Phase 107, 116, 119).

**Phase 123 addendum -- Ice-Suspend narrative cluster.** `SAY.PAS`
lines 637-646, immediately following `_LSIBers` and immediately
preceding `_LUndWF` (`Sps(Fireball,S_PCom)`): the full narrative
sequence around `Spell.ICE_SUSPEND`'s own effect (the cast itself,
`_LCIceS`, is already `SPELL_CAST_ANNOUNCEMENT[Spell.ICE_SUSPEND]`,
Phase 122). Eight real, single, hardcoded templates (no file), each a
distinct moment in the same encounter: cast -> held in ice / breaks
free -> fall damage or immunity -> stalemate options.

- `_LPIce: Say('but the shell/Rice was not strong/Rthick enough to
  hold/Rstop [, and [1 began to break_out/Rcrack_through.',S_PCom)` --
  the ice fails to fully hold the target, who begins breaking free
  immediately after being cast on. `render_ice_suspend_failed_to_hold()`.
- `_LBIce: Say('< struggled/Rattempted to break out of > {frosty
  }shell/Rprison of {cold/Rfrigid }ice.',S_PCom)` -- the target's own
  break-out *attempt* (not yet resolved). `render_ice_break_out_attempt()`.
- `_LFIce: Say('with a mighty heave/Reffort, < broke out of > {frosty
  }shell/Rprison of {cold/Rfrigid }ice.',S_PCom)` -- the target's
  *successful* break-out. `render_ice_break_out_success()`.
- `_LIceCr: Say('[1 dropped/Rcrashed, suffering/Rtaking # damage
  points.',S_PCom)` -- fall damage after the ice releases/shatters,
  `#` is `PROSE.TXT`'s own damage-points marker (same convention as
  `render_attack_hit()`, Phase 112). `render_ice_fall_damage()`.
- `_LIceGh: Say('but ['s translucent form easily glided through the
  ice.',S_PCom)` -- an incorporeal/ghost-type target is immune to the
  ice entirely. `render_ice_ghost_immune()`.
- `_LShIce: Say('[1 was immobilized_by/Rlocked_in the {frosty
  }shell/Rprison of {cold/Rfrigid }ice.',S_PCom)` -- the immobilized
  *state* itself, distinct from the cast announcement.
  `render_ice_immobilized()`.
- `_LWMelt: Say('< stood away from [ and waited for the ice to
  melt.',S_PCom)` -- the opponent's own tactical choice not to attack
  a frozen target and instead wait it out. `render_ice_wait_for_melt()`.
- `_LSFroz: Say('< could not take the ^L\\ because what [1 carried was
  frozen in with [.',S_PCom)` -- a blocked Steal/Take-item attempt
  against a frozen target; `^L\\` is `report/prose.py`'s own
  list-insertion (Phase 118) over `PROSE.TXT`'s `\\` (Magic Item)
  marker, the same shape `render_take_items()` (Phase 118) already
  established. `render_ice_steal_blocked()`.

No source ties these eight moments into a single fixed sequence (e.g.
whether `_LBIce` always precedes `_LFIce`, or whether `_LPIce` is a
same-turn alternative to `_LShIce` rather than a strict predecessor)
-- each is exposed as its own renderer, the caller sequences them
according to the encounter's own real outcome, the same
caller-decides-the-sequence stance already taken for the
`_ADishK`/`_ADishF` pair (Phase 121) and the `_LCast1`/
`SPELL_CAST_ANNOUNCEMENT` pair (Phase 122).

**Phase 124 addendum -- end-of-turn Financial Report.** `RUMORS.PAS`'s
own story-code `CONST` block groups `_LRev = 3055`, `_LLCosts = 3056`,
`_LACosts = 3057`, `_LFinance = 3058`, and `_LTreas = 3063`
contiguously (with `_LCHoly`/`_LCHOD`/`_LCPsyBl`/`_LCInvis` -- already
`SPELL_CAST_ANNOUNCEMENT` entries, Phase 122 -- interleaved at
3059-3062); `_AUnpaid = 4013` sits in the separate "Army" 4000s block
but is the same topical narrative (`SAY.PAS` lines 835-840, all five
sentences physically adjacent). Five real, single, hardcoded templates
(no file) making up the complete end-of-turn financial summary every
kingdom receives -- the first narrative in this module tied to
`GameState`'s own `KingdomState.treasury` field (Phase 9) and
`turn/recruit_execution.py`'s own already-modeled treasury spending
(Phase 15).

- `_LFinance: Say('here is the financial report for <''s kingdom:
  ',S_Red)` -- the section's opening clause.
  `render_finance_report_opening()`.
- `_LRev: Say('this turn, the Kingdom collected # gold in
  revenue.',S_Red)` -- `#` is `PROSE.TXT`'s own numeric marker (same
  convention as `render_attack_hit()`, Phase 112).
  `render_finance_revenue()`.
- `_LLCosts: Say('# gold was expended to finance our
  leaders.',S_Red)` -- leader upkeep cost. `render_finance_leader_costs()`.
- `_AUnpaid: Say('unfortunately, #% of your Majesty''s armies had to
  go without pay.',S_Red)` -- `#%` is the same `#` marker, here a
  percentage rather than a gold amount; this project has no source for
  when this sentence is included versus omitted (it's presumably
  conditional on at least one army actually going unpaid), so the
  caller decides whether to call it at all, the same
  caller-decides-inclusion stance `render_attack_devastating_hit()`
  (Phase 112) already established for its own conditional sentence.
  `render_finance_unpaid_armies()`.
- `_LACosts: Say('# gold was expended to maintain our
  armies.',S_Red)` -- army upkeep cost. `render_finance_army_costs()`.
- `_LTreas: Say('< was left with # gold in the treasury.',S_Red)` --
  the closing balance, ties directly to `KingdomState.treasury`'s own
  post-turn value. `render_finance_treasury()`.

No source stitches these five into one combined sentence -- `SAY.PAS`
dispatches each as its own `Say()` call in sequence, so each is its
own renderer here too, matching the plain sequential-report shape
already established for `render_spy_*()` (Phase 115).

**Phase 125 addendum -- Assassination narrative.** `RUMORS.PAS` groups
`_AKill = 3367`, `_ASeek = 3368`, `_AFail = 3369` contiguously
(`SAY.PAS` lines 958-970); `_LOAss = 3392` sits separately but is the
same topical narrative (`SAY.PAS` line 958, immediately before
`_ASeek`'s own block starts). Ties to `models/office.py`'s own
`OFFICE_PERK_DESCRIPTION[Office.ASSASSIN] == "Free Assassination
Attempt"` (Phase 103) -- the first narrative content confirming that
perk's own real-game mechanic. **Wired as of Phase 614** into
`turn/assassin_guild.py resolve_pending_guild_assassination()` (via
`describe_turn_results()`'s own `GuildAssassinationOutcome` branch
below) -- see that module's own docstring for the disassembly source
that finally confirmed the FI-order interception these four sentences
narrate.

- `_LOAss: Say('< ordered the assassination of [.',S_Priv)` -- the
  order/directive itself. `render_assassination_ordered()`.
- `_ASeek: Say('While [1 was out_for_a_stroll/Rin_meditation, suddenly
  an{ unknown} assassin launched himself{ from out of the dark} at
  [!',S_Adv)` -- the attempt begins. `render_assassination_attempt()`.
- `_AKill: Say('[1 was wounded/Rstabbed by a_poisoned/Rhis_poisonous
  dagger!Cursed be the Assassin''s Guild and whoever heads
  it!',S_Adv)` -- the attempt **succeeds**.
  `render_assassination_success()`.
- `_AFail: BEGIN Say('Fortunately, [1 survived the attempt and the
  assassin (apparently, a member of the Assassin''s Guild) was
  killed.',S_Adv); Say('Of_course/RWithout_delay, the guard
  in/Rthroughout [''s kingdom was {immediately }doubled.',S_Adv); END`
  -- the attempt **fails**, a real two-`Say()` entry concatenated with
  no separator, the same shape established throughout this module
  (Phase 107, 116, 119, 121). `render_assassination_failed()`.

Success versus failure is now a real, sourced roll (Phase 614,
`turn/assassin_guild.py grandfather_of_assassins_base_success_chance()`),
not a caller-supplied fact -- superseding this paragraph's own
pre-Phase-614 "no source" stance.

**Phase 614 addendum -- the dead-and-buried case.** `ILLEG.X2` record
91: `'[1 could not be assassinated because [1 was dead and buried.'` --
the real message when the queued target already died some other way
before phase-5 resolution (`AK.EXE:0x18D89`'s own `Alive(victim)`
recheck). `render_could_not_be_assassinated()`.

**Phase 126 addendum -- battle morale narrative + vampiric bite.**
`RUMORS.PAS` groups `_BSpeech = 4046`, `_BHome = 4047`, `_BNoDru =
4048`, `_BRWeap = 4049`, `_BBluff = 4050`, `_BNoEx = 4051`
contiguously; `_BFun = 3326` and `_LChUnd = 3327` sit together in a
separate, earlier block (`SAY.PAS` lines 1160-1188). This addendum
covers every real, hardcoded (no-file) entry from both groups;
`_BNoDru` (`FD('nodru',S_Batt,1000+Rint)`) and `_BBluff`
(`FD('bluff',S_Batt,1)`) are file-dispatched and deliberately left for
a future phase that extracts `NODRU.X`/`BLUFF.X`.

- `_BFun: Say('The Skeletal Armies led by < marched into battle with a
  fanatical fervor.',S_Batt)` -- ties directly to `Spell.SKELETAL_ARMY`
  (already `SPELL_CAST_ANNOUNCEMENT`, Phase 122).
  `render_skeletal_army_fervor()`.
- `_BSpeech: BEGIN Set_Excldr; Say('using/Rcalling_upon > magical/Rarcane
  powers/RSpell of Oratory, ',S_Priv); _excldr:= -1; Say('< gave/Rstarted_with
  \x01 rousing/Rinspiring speech/Rharangue to > troops/Rarmy,
  raising/Rwhich_bolstered their courage/Rmorale.',S_Batt); END` -- a
  real two-`Say()` entry, concatenated with no separator (Phase 107,
  116, 119, 121, 125); `\x01` is `PROSE.TXT`'s own `^A` (indefinite
  article) marker. Ties to `Spell.ORATORY` (already
  `SPELL_CAST_ANNOUNCEMENT`, Phase 122). `render_oratory_speech()`.
- `_BHome: Say('<''s troops/Rsoldiers were_prepared/Rswore to
  fight/Rstruggle desperately/Rlike_tigers for their
  homeland/Rfatherland.',S_Batt)` -- home-province defensive morale.
  `render_homeland_defense_morale()`.
- `_BRWeap: Say('< waved/Rheld_aloft > \\ and the/R> \x12
  cheered_wildly/Rwere_virtually_hypnotized{ with/Rin
  admiration/Rit''s_enchanted_glow}!',S_Batt)` -- a leader rallies
  troops by brandishing a magic item; `\\` is the Magic Item marker,
  `\x12` is `PROSE.TXT`'s own `^R` (Race name) marker, already
  established by `models/race.py RACE_NAME` (Phase 87). The `the/R>`
  alternation picks between a bare article and the leader's own
  possessive -- resolved by `report/prose.py`'s existing `/R`-then
  -substitution pipeline exactly as documented (no new capability
  needed). `render_weapon_rally()`.
- `_BNoEx: Say('< couldn''t/Rfailed_to think_of/Rcome_up_with a
  good/Rbelievable excuse/Rploy for_avoiding/Rto_get_out_of the duel,
  so ',S_Batt)` -- a precursor clause (no trailing period, ends in
  "so ") that `SAY.PAS` concatenates with further content, ties to
  `turn/duel.py`'s own Duel-avoidance concept. Exposed as a bare
  `DUEL_NO_EXCUSE_TEMPLATE` constant with no wrapper function, the
  same shape `EXPLORE_NOT_PRESENT_PREFIX` (Phase 110) already
  established for an unstitched precursor.
- `_LChUnd: Say('< sank/Rbit > fangs into [ and drained/Rsucked_up
  {all }] blood.[1 changed to $o alignment!',S_Prev)` -- a vampiric
  bite that changes the victim's alignment; `$o` is `PROSE.TXT`'s own
  Alignment/outlook-name marker, already established by
  `models/power.py` (Phase 95/101). `render_vampiric_bite()`.

**Phase 127 addendum -- illegal-move error narrative.** `SAY.PAS`'s
main `Say_Code` `CASE` (~lines 1309-1325) also dispatches on raw
numeric codes outside `RUMORS.PAS`'s named 3000-9999 story-code
block -- `Say_Code` itself (`RUMORS.PAS` ~line 1685) confirms `code >=
32500` as a real, valid dispatch range (`(code >= 32500) or ((code >=
3000) and (code <= 9999))`), so codes `32500`/`32501` are dispatched
system/validation-error narratives, not orphaned CASE labels. These
tie directly to two already-built validation mechanics:
`turn/contested_province.py is_illegal_move_from_contested()` (Phase
36) and the non-adjacent-move chase concept (Phase 78/85, rulebook
[3.1]).

- `32500: Say('< tried to move from \x13 to @, a non-adjacent
  province.This is illegal!',S_Priv)` -- `\x13` is `PROSE.TXT`'s own
  `^S` (Province name #2) marker, the origin. `render_illegal_move_
  non_adjacent()`.
- `32501: BEGIN _next:= Rint; IF _next <> 5 THEN Say('< attempted an
  illegal move.',S_Priv); CASE _next OF ... END; END` -- a generic
  prefix (`render_illegal_move_attempted()`) followed by one of four
  real sub-case sentences, keyed by `_next`'s own range:
  - `-1: Say('< could not retreat into an occupied
    province.',S_Priv)`. `render_illegal_move_occupied_retreat()`.
  - `100..149: Say('< tried to use water-borne movement to move from
    \x13 to @, but > transport was insufficent for the
    task.',S_Priv)` (verbatim "insufficent", the source's own
    misspelling, kept as transcribed). `render_illegal_move_
    insufficient_water_transport()`.
  - `150..199: Say('< tried to move from \x13 to @, but provincial
    flooding and insufficient transport thwarted the
    move.',S_Priv)`. `render_illegal_move_flooding_transport()`.
  - `200..249: Say('< was ordered to move with Mermen from \x13 to @,
    but had insufficient air-transport.',S_Priv)` -- "air-transport"
    for Mermen is the source's own literal text (not "corrected" to
    "water-transport"; this project transcribes verbatim, flags
    honest oddities rather than silently fixing them, the same stance
    already taken for `_LDevast`'s discrepancy, Phase 112).
    `render_illegal_move_mermen_air_transport()`.
  - The `ELSE` branch (`FD('c:\\tp\\prose\\illmove.x2', ...)`) is
    file-dispatched -- `ILLMOVE_TEMPLATE` (Phase 583, below) now
    transcribes it, keyed by raw file position (`_next+1`) rather than
    by scenario, since the exact `_next` value that reaches each of the
    21 real entries has no traceable source.

This project has no source for how `render_illegal_move_attempted()`
and a specific sub-case sentence combine (e.g. whether both are always
shown, or the generic prefix is skipped for some `_next` values beyond
the documented "`_next <> 5`" condition) -- each is exposed as its own
renderer, the caller composes them, the same caller-composes-the
-sequence stance already taken for the Ice-Suspend cluster (Phase 123)
and the Assassination cluster (Phase 125).

**Phase 129 addendum -- Monster Quest Fulfillment dialogue.**
`RUMORS.PAS` groups `_LFRaid = 3166` through `_LFRumor = 3193`
contiguously (`SAY.PAS` lines 764-782) -- direct-speech ("Sayeth...")
dialogue between a quest-giving monster and the character trying to
fulfill its quest, dispatched alongside the file-routed `_LSpake
-> FULFILL.X2`/`_MReply -> MTALK.X2`/`_LRidAns -> RANS.X` (all keyed
by `_qplotno`/`_qsubplot`, an unmodeled Quest-plot system -- narrative
modeled independently of it, the same precedent already established
for the Ice-Suspend cluster, Phase 123, and Assassination, Phase 125).
Ties to `models/advanced_ability.py AdvancedAbility.DRUIDIC_TRADES`'s
own "GI-ve" order description, which already covers the mechanical
side of trading with a monster (Phase 128).

Marker convention confirmed consistent across the whole cluster:
`<` is the character, `[`/`[1` is the quest-giving monster (e.g.
`_LFKOnly: Say('But as < approached [, < lost > courage and ran away
from [.',S_PCom)` unambiguously has `<` doing the approaching/
fleeing and `[` being approached/fled-from).

- `_LHaHa: Say('snarleth/Rchortled [1, "Ha!You fool/Rbumpkin,
  I''ve tricked/Rdeceived you!',S_PCom)` -- opens a quote with no
  visible closing `"` anywhere in this CASE block; transcribed
  honestly as the fragment it is. **Phase 582 correction**: this
  docstring previously guessed the quote was "likely closed by
  `_LRidAns`'s own file-dispatched `RANS.X`... but this project has no
  access to that file's content to confirm" -- a byte-faithful
  reconstruction of the full prose corpus (`AKPROSE_reverse_
  engineering_report.md`, supplied directly by the user) now gives real
  access to `RANS.X`'s own content, and it does *not* close this quote:
  every one of `RANS.X`'s 7 entries is a "yes, that's the correct
  answer" congratulation ("Sayeth [, 'Yes, ...is the correct answer!
  You're very good at this game.'"), semantically unrelated to the
  mocking "I've tricked you" fragment above. The hypothesis is
  withdrawn; the quote remains a genuine, unexplained fragment.
  `render_quest_mockery()`.
- `_LBThen: Say('But then ',S_PCom)` -- a bare precursor clause (no
  trailing period), exposed as `QUEST_BUT_THEN_TEMPLATE` with no
  wrapper function, the same shape `EXPLORE_NOT_PRESENT_PREFIX`
  (Phase 110) already established.
- `_LWGrr`/`_LPrDie` -- a confirmed real two-`Say()` pair: `_LWGrr`
  opens a quote it never closes ("...respect!"), and `_LPrDie`'s own
  text starts lowercase and ends with the missing closing `"`
  ('now, prepare/Rget_ready to die/Rmeet_your_maker!"') -- the same
  concatenation evidence pattern (lowercase continuation + closing
  punctuation) already used to confirm `_LCast1`/`SPELL_CAST_ANNOUNCEMENT`
  concatenate (Phase 122). `render_monster_threat_death()`.
- `_LWTake`/`_LWErrand` -- each opens a quote with no visible closing
  `"` (unlike `_LWGrr`, no later CASE label in this block picks up
  their own continuation) -- transcribed honestly as fragments.
  `render_quest_item_taken_anyway()`/`render_quest_errand_thanks()`.
- `_LFWrong`, `_LFProgr`, `_LFNQual`, `_LFNoPri`, `_LFTryAg`,
  `_LFHero`, `_LFNoAg`, `_LQDone` -- eight complete, self-closing
  quoted sentences (each has both an opening and closing `"`),
  covering the quest's own outcome states: wrong answer, partial
  progress acknowledged, insufficient skill, insufficient price,
  service not performed, an unsatisfactory "Hero" offering, no prior
  agreement existed, and the quest reward already given to someone
  else (`_LQDone`'s own `\\` marker is `PROSE.TXT`'s Magic Item name).
  `render_quest_wrong_answer()`/`render_quest_progress_acknowledged()`/
  `render_quest_insufficient_skill()`/`render_quest_insufficient_price()`/
  `render_quest_service_not_performed()`/`render_quest_hero_not_tasty()`/
  `render_quest_no_agreement()`/`render_quest_reward_already_given()`.
- `_LFKOnly: Say('But as < approached [, < lost > courage and ran
  away from [.',S_PCom)` -- plain narration (no quotes), the
  character's own courage fails during the quest encounter.
  `render_quest_fled_in_fear()`.

**Phase 582 addendum -- the file-dispatched half of the same cluster.**
Four small catalogs this project previously had no access to
(`RIDDLE.X2`/`VISIT.X2`/`FUVIS.X2`/`RANS.X`, all `_qsubplot`-keyed, per
the intro paragraph above) are now transcribed from the same byte-
faithful reconstruction that corrected the `RANS.X` hypothesis just
above. Each catalog's own choice order matches an existing `Treasure`
enum group exactly, confirmed positionally (e.g. `RIDDLE.X2` choice 7,
"What goes on four legs in the morning, two at midday and three legs
in the evening?", is the classic Riddle of the Sphinx -- the answer is
"Man", matching `Treasure.QUEST_RA_MAN`'s own name exactly):

- `QUEST_RIDDLE_TEXT`/`QUEST_RIDDLE_ANSWER_TEXT` (`RIDDLE.X2`/`RANS.X`,
  7 entries each) key by the 7 `Treasure.QUEST_RA_*` members
  (`QUEST_RA_RIDDLE`..`QUEST_RA_MAN`) -- the riddle itself (`RIDDLE.X2`,
  routed via `RUMORS.PAS`'s own `⟦CTRL-G⟧` byte, embedded in `MTALK.X2`'s
  own `R_RIDDLE` entry as `⟦CTRL-G:riddle⟧`) and the monster's own
  "correct!" congratulation (`RANS.X`) once the right answer is given.
- `QUEST_VISIT_TEXT`/`QUEST_VISIT_FULFILLED_TEXT` (`VISIT.X2`/
  `FUVIS.X2`, 5 entries each) key by the 5 non-riddle "go somewhere and
  do something" `Treasure` quest-item ordinals (`QUEST_SNOW_QUEST`,
  `QUEST_SAPPH_RING`, `QUEST_LUCKY_PENNY`, `QUEST_GODS_QUEST`,
  `QUEST_MERMAID_AMULET`) -- the monster's own travel directions
  (`VISIT.X2`, routed via `RUMORS.PAS`'s own `⟦CTRL-U⟧` byte, embedded
  in `MTALK.X2`'s own `R_VISIT` entry as `⟦CTRL-U:visit⟧`) and the
  narration of what happens once the character actually visits
  (`FUVIS.X2`, `SAY.PAS:785 _LFuVis`).

**Stored as raw template text, unlike every other Phase 129 constant
above.** Every `QUEST_*_TEMPLATE` earlier in this addendum went through
`render()` because each is fully within that function's own documented
scope (`/R`/`{...}` alternation, plain `[`/`[1` substitution). These
four catalogs additionally contain real `⟦CTRL-A⟧`/`⟦CTRL-X⟧`/`⟦CTRL-G⟧`
control-byte codes and `$+` list markers `render()` has no defined
behavior for (`report/prose.py`'s own module docstring covers only the
symbols it implements) -- rendering them through `render()` as-is would
either raise or silently mishandle the placeholder, so they are left
as sourced, unrendered strings instead, the same "no consumer wired
yet" posture `turn/encounter.py MONSTER_TALK_OFFER_TEXT` (Phase 581)
already took for the identical reason.

**Phase 130 addendum -- monster raid-truce offer.** `RUMORS.PAS`'s
`Check_Raid` procedure (~lines 2279-2286), dispatched inline within
`FD`'s own `MTALK.X2` file-dispatch flow (the same file `_MReply`
routes to in the Phase 129 cluster) rather than from the main
`Say_Code` `CASE`: `IF dex > 1000 THEN IF not offer_stop_raid THEN IF
fn = 'mtalk' THEN IF fstate[_feat1-256]=Bold THEN IF ((ldesc = '') or
(ldesc[1] = '(')) THEN BEGIN offer_stop_raid:= true; Say('[ also
offered to stop raiding/Rplundering @ if this quest be/Rwere
accomplished/Rcompleted.',S_PCom); END;` -- a single, real, hardcoded
template, gated on the guarding monster's own `fstate` being `Bold`
(`models/monster.py MonsterEngagementState.BOLD`, "Emboldened",
Phase 130). `render_monster_offers_raid_truce()`.

**Phase 133 addendum -- Trade/Give narrative cluster.** Found while
verifying real domain knowledge the user supplied directly about the
Give order's item-vs-gold disambiguation mechanic (see `turn/
trade_decode.py`'s own Phase 133 correction) against the Pascal
source: `SAY.PAS` ~lines 517-520, four single, real, hardcoded
templates (no file), all previously unrendered:

- `_LTrade: Say('< gave the \\ to [.',S_Priv)` -- a successful item
  Give. `render_item_give()`.
- `_LGGive: Say('< gave/Rdonated to [ # gold from > treasury/Rown_funds.',
  S_Priv)` -- a successful gold Give (`turn/trade_execution.py
  execute_give()`'s own success case). `render_gold_give()`.
- `_LNHave: Say('< didn''t have on hand the full # gold requested, so ',
  S_Red)` -- insufficient gold, matching the user's own described
  failure case almost verbatim ("l'eroe #55 non aveva con se
  abbastanza oro da darti"). Transcribed as-is, including its trailing
  "so " -- the same honest-fragment-transcription convention as
  `_LHaHa`/`_LWTake`/`_LWErrand` (Phase 129): no continuation is found
  anywhere else in the available source, so none is invented.
  `render_insufficient_gold()`.
- `_LNDeal: Say('< could not strike a deal with [ for the \\.',S_Priv)`
  -- a reciprocal two-way trade's condition not met (rulebook [3.18]:
  "the gift will be made only if the recipient Gives you a specified
  magic item... in the same phase"). `render_trade_deal_failed()`.

**Phase 155 addendum -- monster missile-attack flavor text and Troll
regeneration narration, project-original.** `Desktop/MOSTRI con
statistiche.txt` (Phase 154's own combat-stats source, confirmed by the
user to be their own compilation, not a Pascal transcription) gives
four numbered footnotes describing narrative variants for specific
monsters' Fire Arrow-equivalent missile attacks, quoted in full
(translated from the user's own Italian) and implemented as six new,
single-template renderers (no ``pick_variant`` list -- only one wording
was supplied per case, unlike every sourced ``PROSE.TXT`` template in
this module):

- **Breath weapon** (dragons, Chimera): "The dragons' Fire Arrow is
  comparable to the dragon's breath, but the effect is that of an arrow
  with slightly boosted damage. The only difference is what gets
  printed when the missile is loosed." Hit: "The (dragon type or
  Chimera) breathes, and the impact deals X damage." Miss: "...breathes,
  but (hero or King name) miraculously manages to evade it!"
  `render_breath_weapon_hit()`/`render_breath_weapon_missed()`.
- **Boulder throw** (Giant/Treant/Titan, per the footnote's own text):
  "Giant, Treant, and Titan throw large boulders... same effect as an
  arrow with slightly boosted damage." Hit: "The (giant type) hurls a
  huge boulder, and the impact deals X damage." Miss: "...hurls a huge
  boulder, but (name) dodges it." `render_boulder_throw_hit()`/
  `render_boulder_throw_missed()`.
- **Petrifying gaze** (Basilisk, Medusa): "Basilisk and Medusa petrify
  with their gaze... same effect as an arrow with slightly boosted
  damage." Hit: "The (petrifier type) casts a petrifying gaze, and
  (hero or King) takes X damage." Miss: "...casts a gaze, but (name)
  evades it." `render_petrifying_gaze_hit()`/
  `render_petrifying_gaze_missed()`.
- **Troll regeneration** (``turn/encounter.py``'s own Phase 155
  addendum for the mechanical half): "The combat message reads:
  'Horror! The Troll is regenerating its wounds.'"
  `render_troll_regeneration()`.

`missile_attack_flavor(weapon)` classifies a monster's own
``models/weapon.py MONSTER_RANGED_WEAPON`` assignment (Phase 94,
real, ``CTME.PAS``-sourced) into one of the three categories above --
``Weapon.FLAME_BREATH``/``SPIT_ACID``/``POIS_BREATH`` -> breath weapon,
``Weapon.BOULDER`` -> boulder throw, ``Weapon.GAZE`` -> petrifying gaze,
``None`` for everything else (falls back to the generic
``render_fire_arrow_attack()``/``render_attack_hit()``/
``render_attack_missed()`` triplet, Phase 111-112).

**A genuine, documented cross-source discrepancy, not resolved either
way**: the footnote's own text says Giant, Treant, *and* Titan all
throw boulders, but ``MONSTER_RANGED_WEAPON`` (real, ``CTME.PAS``-
sourced, Phase 94) gives `Monster.TITAN` and `Monster.TREANT` both
`Weapon.NO_WEAP` -- no ranged attack at all -- while only
`Monster.GIANT` maps to `Weapon.BOULDER`. `missile_attack_flavor()`
follows the confirmed Pascal-sourced weapon table, not the footnote's
own broader claim, the same "don't let a less-rigorously-sourced
document silently override already-cited Pascal data" policy `models/
monster.py`'s own Phase 154 addendum used for the Spectre hit-point
discrepancy. Titan and Treant's own `MONSTER_COMBAT_STATS` missile
stats (Phase 154) stay populated but structurally unreachable through
this dispatch, exactly like the rest of this module's already-documented
unreachable-data cases.

**Phase 156 addendum -- Search's own report composer.** `describe_*()`
existed for every other real-execution action (Hire/Fire/Cast/Use_MI/
Practice/Give, Phases 142-144) except Search, even though `turn/
search_execution.py execute_search()` (Phase 132) has run real combat
since before any of them. Found by re-scanning `SAY.PAS` for
Search-specific dispatch, past `RUMORS.PAS`'s own now-fully-mined
`Say_Code` block: `_LSearch: FD('fsearch',S_Adv,10)` -> `FSEARCH.X`
(5 real templates, the Search-attempt opening sentence -- "approached
the &, intending to root out its mysteries", etc.) and `_LSacked: Say('<
searched/Rscouted_out the & but it {apparently }had {already }been
looted/Rsacked.',S_Adv)` (a single, real, hardcoded template for
attempting to Search an already-looted feature) -- both real and
declared, neither with a confirmed live dispatch site in the surviving
`.PAS` files (the same "the calling main program is itself missing"
status most templates in this module already carry, not a reason to
discard them). `render_search_attempt()`/
`render_search_feature_already_sacked()`, `describe_search()`.

`describe_search()`'s own combat-outcome half reuses `render_
mortally_wounded()` (Phase 112) for a fatal loss -- personal combat's
generic [5.0] death rule, the same reasoning `turn/search_execution.py`'s
own docstring already gives. A win or an inconclusive fight append
nothing further: no sourced "you defeated the guardian, the treasure is
yours" sentence exists anywhere in the available archive -- the same
confirmed-absent conclusion Phase 148's own research already reached
for the adjacent skill-book-read moment (`TREASAB.X2`/`TREASURE.X2` are
inventory-view text, not a Search-victory narration).

**Phase 213: now wired into `describe_turn_results()`**, alongside
PURSUE/TRAIL/ASPY -- see that function's own Phase 213 note for how
(a new `SearchExecutionResult.request` field, stamped by
`plan_dispatch.py`'s own dispatcher). `describe_search()` stays
directly callable by anyone who still has the original
`SearchRequest`/`Feature` in hand.
"""

from __future__ import annotations

import random
from typing import Sequence

from ak_engine.models.enums import (
    ActionCode,
    ABILITY_NAME,
    Ability,
    CAST_SPELL_OPENING_COMPLETE_SPELLS,
    CAST_SPELL_OPENING_COMPLETE_TEMPLATE,
    CAST_SPELL_OPENING_CONTINUED_TEMPLATE,
    SPELL_CAST_ANNOUNCEMENT,
    SPELL_NAME,
    Spell,
)
from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import ALIGNMENT_ABBREVIATION, ALIGNMENT_BY_ORDINAL, ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.army_naming import make_army_name
from ak_engine.models.army_type import (
    ARMY_TYPE_DESIGNATION,
    ARMY_TYPE_NAME,
    MONSTROUS_ARMY_RACE,
    ArmyType,
    is_overflight_unit,
)
from ak_engine.models.feature import FEATURE_TYPE_NAMES, Feature
from ak_engine.models.game_state import ArmyState, GameState, LeaderState, ProvinceState
from ak_engine.models.magic_feature import MAGIC_FEATURE_NAME, MagicFeature
from ak_engine.models.map import TERRAIN_NAME, HexCoord, Terrain, province_code
from ak_engine.models.monster import MONSTER_DESCRIPTION, MONSTER_NAMES, Monster
from ak_engine.models.office import OFFICE_MIN_POINTS, OFFICE_NAME, Office
from ak_engine.models.power import Power
from ak_engine.models.quote import quote_of_the_week
from ak_engine.models.race import HUMANOID_RACES, RACE_NAME, Race
from ak_engine.models.rumor import Rumor, RumorContent
from ak_engine.models.discovery import DISCOVERY_NAME, Discovery, describe_discovery_line, sorted_kingdom_discoveries
from ak_engine.models.sex import Sex
from ak_engine.models.temper import TEMPER_ABBREVIATION, TEMPER_NAME
from ak_engine.models.treasure import GOLD_HOARD_DISPLAY_NAME, TREASURE_CATEGORY, TREASURE_LABEL, TREASURE_NAME, Treasure, TreasureCategory
from ak_engine.models.weapon import MONSTER_RANGED_WEAPON, Weapon
from ak_engine.report.ascii_map import (
    LAYOUT_TIERS,
    MAP_REGION_LABEL_RULE,
    map_region_label,
    max_columns_per_page,
    paginate_known_columns,
    select_layout_tier,
)
from ak_engine.report.prose import render
from ak_engine.turn.assassin_guild import GuildAssassinationOutcome
from ak_engine.turn.army_quality import compute_army_modified_quality
from ak_engine.turn.aspy_defend_decode import DefendRequest
from ak_engine.turn.aspy_execution import SpyReport
from ak_engine.turn.battle_orchestrator import BattleReport, QualityChange, find_king_of_kingdom
from ak_engine.turn.defend_execution import DefendReinforcement
from ak_engine.turn.battle_luck import (
    bluck_cluck_uses_secondary_catalog,
    column_narration_eligible,
    render_bluck_event,
    render_cluck_event,
)
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult
from ak_engine.turn.cast_execution import CastExecutionResult, is_unfinalized_royal_heir
from ak_engine.turn.challenge_execution import ChallengeExecutionResult
from ak_engine.turn.combat import QUALITY_NAME
from ak_engine.turn.emperor_election import _ORDINARY_ALIGNMENTS, alignment_victory_point_reduction_percent
from ak_engine.turn.final_standings import compose_final_standings_report
from ak_engine.turn.encounter import CombatRange, FireArrowShot
from ak_engine.turn.exploration import ExploreResult
from ak_engine.turn.move_execution import MoveExecutionResult
from ak_engine.turn.hex_numbering import decode_hex_number, encode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, hex_distance_wrapped
from ak_engine.worldgen.place_map import DEFAULT_WIDTH
from ak_engine.turn.discovery_effects import effective_skill_level, emperor_holds_arcanes_valor_unification
from ak_engine.turn.expenses import MaintenanceResult, compute_expected_expenses, leader_pay
from ak_engine.turn.valhalla_execution import VALHALLA_VISITOR_RULES_TEMPLATE
from ak_engine.turn.office_holder import (
    ALL_OFFICES,
    OfficeHolder,
    kingdom_best_candidate,
    kingdom_runner_up,
    leader_office_rank,
    office_rival_best_points,
    resolve_office_holder,
)
from ak_engine.turn.plan_dispatch import (
    ArmyListExecutionResult,
    FireExecutionResult,
    HireExecutionResult,
    PhaseDispatchResult,
)
from ak_engine.turn.practice_execution import MAX_SKILL_LEVEL, PracticeExecutionResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.recruit_execution import RecruitExecutionResult
from ak_engine.turn.feature_power_execution import FeaturePowerAttemptResult
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.tax_base import compute_invention_bonus_percent, compute_tax_base, province_tax_yield
from ak_engine.turn.trade_execution import TradeExecutionResult
from ak_engine.turn.trail_execution import KingIntelligence, TrailExecutionResult
from ak_engine.turn.use_mi_execution import UseMIExecutionResult
from ak_engine.turn.world_events import is_visible_to

# HostAK/TP/PROSE/PLUS1.X .. PLUS5.X, MINUS1.X .. MINUS5.X, ZERO.X --
# transcribed verbatim (mini-language intact), PROSE.TXT notation for the
# control-byte markers (see module docstring). Every line keeps its
# original leading space: these are appended directly after a subject
# clause ("<army> fought with <army> and<sentence>"), never used stand
# -alone.
_MARGIN_TEMPLATES: dict[int, list[str]] = {
    -5: [
        " were cut/Rmowed down like cattle/Rsheep.",
        " were sliced and diced like ^A knife/Rblade cutting through butter/Rlard.",
        " had their booties/Rswords kicked {all the way }up their throats.",
    ],
    -4: [
        " were beaten_down/Rtrampled_over like overripe/Roversized pumpkins/Rwatermelons.",
        " were easily/Reffortlessly overrun/Rbeaten by the enemy.",
        " were knocked out of the battle/Rfight by the enemy's ferocious/Rfanatical charge/Sattack.",
    ],
    -3: [
        " was {almost }powerless to stop/Rhalt their {determined }advance.",
        " was forced to retreat in disorder/Rdisarray.",
        " buckled/Rcrumpled under the heavy attack/Rpressure, retreating in disarray/Rdisorder.",
    ],
    -2: [
        " could not stop their steady/Rdetermined advance.",
        " fought courageously/Rbravely, but was steadily pushed back.",
        " could not stand_their_ground/Rhold_the_line and executed/Rconducted a_fighting/Ran_orderly retreat.",
    ],
    -1: [
        " gradually gave_ground/Swas_pushed_back.",
        " were {slowly }bent/Spushed back by their attack/Rpressure.",
        " could not {quite }hold their ground/Sown against their savage/Rdetermined foe/Ropponent.",
    ],
    0: [
        " fought/Rbattled them to ^A standstill.",
        " fought/Rbattled them tooth and nail, neither side/Sfleet willing to give ground/Sup.",
        " could neither gain the upper_hand/Radvantage nor could the enemy make any progress/Rheadway.",
        " the fighting here proved/Rwas indecisive/Rinconclusive.",
        " neither army/Sfleet could gain ^A advantage/Redge over the other.",
        " the two armies/Runits slugged/Rfought it out in ^A evenly/Rwell matched"
        "{, indecisive/Rinconclusive} contest/Rbattle.",
    ],
    1: [
        " gradually pushed/Rshoved them back.",
        " was_able/Rmanaged to make some{ slow/Rmeasure_of} progress.",
        " moved/Rground ahead slowly/Rgrimly, contested/Rbattled for every foot/Ryard of their advance.",
    ],
    2: [
        " steadily/Rstout-heartedly advanced against them.",
        " {determinedly }plowed into their opponents.",
        " aggressively/Rquickly knifed into them.",
    ],
    3: [
        " advanced {almost }at will.",
        " drove/Rthrust them back{ with ^A savage fury}.",
        " overpowered/Rovercame them with their thundering/Sdetermined charge.",
    ],
    4: [
        " beat/Rtrampled them down as if they were midgets/Rinvalids.",
        " easily/Rviciously crushed/Rdestroyed them.",
        " lost/Rwasted no time in smashing/Rcrushing their formation/Rlines.",
    ],
    5: [
        " mowed/Rcut them down like weeds/Rbeanstalks.",
        " squashed/Rsmashed them like rotten tomatoes/Roranges.",
        " crushed/Rsmashed their heads/Rskulls as if they were eggshells/Reggplants.",
    ],
}

# HostAK/TP/PROSE/WINNER.X -- attacker wins the battle.
_WINNER_TEMPLATES: list[str] = [
    "the forces of < broke through {the lines of their enemy/Ropposition }and were victorious.",
    "<'s armies/Ssquadrons vanquished/Rshattered the army/Sfleet opposing them with ^A final "
    "{determined }charge/Ssally.",
    "the host/Sfleet of < {finally }broke/Rcrushed the army/Sfleet of ['s morale/Rfighting_spirit "
    "with one last{, great} push.",
    "the battle ended victoriously/Rin_victory for the soldiers/Sships of < as they broke through "
    "{the lines }at ^A critical/Rcrucial moment.",
    "having found ^A weak/Rvulnerable point/Rspot in the line of the host/Sarmada of [, ^A final "
    "savage/Rdetermined thrust/Rslashing_attack finished_off/Rdefeated their enemy/Ropponent and "
    "won the day/Rbattle for <2.",
    "<'s great horde/Sarmada overwhelmed/Roverpowered the army/Sfleet of [ and "
    "took_the_field/Scleared_the_seas_of_their_squadrons, dispersing/Rscattering their enemies.",
]

# HostAK/TP/PROSE/DEFWIN.X -- defender wins the battle.
_DEFWIN_TEMPLATES: list[str] = [
    "the defenders turned_back/Rdefeated <'s forces and drove/Schased them out of @.",
    "<'s armies/Sfleets were beaten/Rdefeated and pushed/Schased out of @.",
    "the attacking Kingdom was defeated {and turned back }in its attempt/Rmove to conquer/Rtake @.",
    "{the host/Sarmada of }the attacking Kingdom was defeated and driven/Rforced out of @.",
]

# HostAK/TP/PROSE/RETREAT.X.
_RETREAT_TEMPLATES: list[str] = [
    "< retreated/Rfell_back to ^S with {the_remnants/Rwhat_remained of }> forces.",
    "< retreated/Rwithdrew {with > command/Rforces }to ^S.",
    "< made/Rset_out for {the safety of }^S with > motley army/SFleet.",
    "< pulled/Rfell back to ^S with{ the_remnants/Rwhat_was_left of} > command.",
    "< withdrew/Rretreated to ^S with > defeated/Rvanquished warriors/Sships.",
    "< retired/Rwithdrew to ^S, beaten/Rdefeated but not broken/Rdiscouraged.",
]

# HostAK/TP/PROSE/KILLARMY.X -- each line keeps its leading space, appended
# directly after the destroying side's name.
_KILLARMY_TEMPLATES: list[str] = [
    " annihilated =.",
    " slew = almost to ^A man.",
    " destroyed =.",
    " demolished =.",
    " scattered = in all directions.",
]

# HostAK/TP/PROSE/PURSUIT.X -- each line ends in "and", meant to be followed
# directly by a KILLARMY sentence (which supplies its own leading space).
_PURSUIT_TEMPLATES: list[str] = [
    "= pursued the enemy and",
    "= gave chase and",
    "= overtook the enemy {in their headlong/Rpanicky retreat }and",
    "= chased after the enemy and",
]

# HostAK/TP/PROSE/DECQ.X, INCQ.X -- a battle-triggered army quality-level
# change (Phase 598). `SAY.PAS:871 _ADecQ: FD('decq',S_Red,10)` and
# `SAY.PAS:870 _AIncQ: FD('incq',S_Red,9)`. `turn/battle_orchestrator.py
# BattleReport.quality_changes: dict[int, QualityChange]` (Phase 423/513's
# own `roll_quality_change()` output, `old`/`new` shape added Phase 610)
# already computes exactly the game-state fact these two templates
# narrate. Wired as of Phase 610 via `describe_quality_changes()` below,
# called from `describe_battle()` -- see that function for the
# DECQ-vs-INCQ dispatch (`new` worse/better than `old`; `new == old`
# entries, i.e. a roll that lands back on the same `Quality`, are
# skipped, since neither template has a real "no change" variant to
# reach for). `⟦CTRL-Q: quality⟧` resolves to `^Q`, its first live use
# in this module (the same never-wired-before pattern `*`/direction hit
# in Phase 594) -- ``quality_name`` is a plain caller-supplied string,
# matching this project's own already-established ``QUALITY_NAME
# [Quality]`` display convention (``turn/combat.py``, Phase 86) rather
# than this function reaching into ``GameState`` itself.
_DECQ_TEMPLATES: list[str] = [
    "= was severely/Rbadly shaken during/Rin the battle and we must "
    "now rate/Rclassify it as ^A ^Q unit.",
    "= took ^A thorough/Rsevere pounding/Rbeating and lost some key "
    "people/Rofficers.It should be considered/Rrated ^A ^Q unit now.",
    "= was unlucky/Runfortunate enough to lose some of its most "
    "able/Rpromising officers{ in personal combat}, and we now "
    "rate/Rrank it ^A ^Q unit.",
    "= had its morale/Rconfidence shaken/Rbattered by ^A bad/Revil "
    "omen which manifested_itself/Rreared_its_ugly_head "
    "during/Rbefore the battle.= has dropped_off/Rslipped in "
    "quality and now it's ^A ^Q unit.",
    "the long{, hard/Rdifficult} campaign caused/Rforced = to lose "
    "some of its battle-lust/Rzeal, and now it can only {be "
    "counted_on/Rtrusted to }fight as ^A ^Q unit.",
    "= was {severely }mauled/Rmangled in/Rduring the battle/Rfight "
    "and has fallen in stature/Rquality to ^Q condition.",
]


def render_army_quality_decreased(army_name: str, quality_name: str, rng: random.Random) -> str:
    """Renders DECQ.X's sentence for an army's quality dropping after a
    battle (Phase 598). Wired into ``describe_battle()`` via ``describe_
    quality_changes()`` as of Phase 610 -- see the module comment above.
    """

    variant = pick_variant(_DECQ_TEMPLATES, rng)
    values = {"=": army_name, "^Q": quality_name}
    return render(variant, values, rng=rng)


_INCQ_TEMPLATES: list[str] = [
    "= proved its mettle/Rvalor in/Rduring the battle/Rfight and we "
    "now rate/Rrank it ^A ^Q unit.",
    "= was greatly buoyed/Rinspired by the victory/Rexciting_battle."
    "We now rate/Rdesignate it ^A {proud }^Q unit.",
    "= was_tested/Rfought_determinedly during the battle and came "
    "through with flying_colors/Ra_good_effort.We can now "
    "call/Rrank it ^A ^Q unit.",
    "we could not have been more_pleased/Rbetter_satisfied with the "
    "elan/Rfighting_spirit of =, and we have elevated/Rraised its "
    "rating/Rranking to ^Q.",
    "the fun_head-bashing/Rmayhem_wreaked by = in/Rduring the "
    "battle has raised/Relevated the spirits/Rmorale of its "
    "warriors/Ssailors, and {all agree that }it has "
    "achieved/Rrisen_to ^Q status/Rquality.",
    "we can {now }raise the rating/Rranking of = to ^Q, its "
    "officers/Rmen having displayed {especially }great/Radmirable "
    "elan/Rcourage.",
]


def render_army_quality_increased(army_name: str, quality_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders INCQ.X's sentence for an army's quality rising after a
    battle (Phase 598) -- the improvement sibling of ``render_army_
    quality_decreased()``. ``is_sea`` (Phase 74) resolves the fifth
    variant's own "/S" marker -- the only one of the twelve DECQ/INCQ
    variants combined that carries one.
    """

    variant = pick_variant(_INCQ_TEMPLATES, rng)
    values = {"=": army_name, "^Q": quality_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


def describe_quality_changes(
    battle_report: BattleReport, army_names: dict[int, str], rng: random.Random, *, is_sea: bool = False
) -> list[str]:
    """Assembles DECQ.X/INCQ.X sentences for every army whose ``Quality``
    genuinely moved during this battle (Phase 610) -- see the module
    comment above ``_DECQ_TEMPLATES`` for the ``BattleReport.quality_
    changes: dict[int, QualityChange]`` shape this reads from.
    ``army_names`` is the same ``build_battle_army_names(state,
    battle_report)`` map ``describe_battle()`` already builds for its
    own per-column/destroyed/retreat sentences -- an army absent from it
    (a sourceless column front unit, see that function's own docstring)
    is skipped here too. An army whose roll landed back on the same
    ``Quality`` (``new == old``) is also skipped, since neither DECQ.X
    nor INCQ.X has a real "no change" variant to reach for.
    """

    lines: list[str] = []
    for army_id, change in battle_report.quality_changes.items():
        name = army_names.get(army_id)
        if name is None or change.new == change.old:
            continue
        quality_name = QUALITY_NAME[change.new]
        if change.new < change.old:
            lines.append(render_army_quality_decreased(name, quality_name, rng))
        else:
            lines.append(render_army_quality_increased(name, quality_name, rng, is_sea=is_sea))
    return lines


# HostAK/TP/PROSE/CONQ.X -- Move conquering an undefended province. All 4
# real variants, transcribed verbatim from the raw file bytes (plain
# ASCII text there, unlike RETREAT.X/WINNER.X's compiled control-byte
# encoding -- see module docstring). Variants 2 and 3 carry a "/S"
# marker (Sea-terrain conditional), resolved as of Phase 74 via
# render_uncontested_conquest()'s own is_sea parameter.
_CONQ_TEMPLATES: list[str] = [
    "<'s forces conquered/Rtook @ without any major battles/Rengagements.",
    "<'s armies/Snaval_forces took control/Rpossession of @ practically uncontested.",
    "@ was conquered/Roverrun{ and occupied} by <'s host/Sfleet.",
    "<'s forces encountered/Rexperienced little resistance/Ropposition in @ and < there established our rule/Rreign.",
]

# HostAK/TP/PROSE/SPY.X -- ASpy's report-opening sentence. "^B"/"^E" are
# transcribed literally (see module docstring: King-exclusion markers,
# elided by render_spy_report_opening rather than resolved).
_SPY_TEMPLATES: list[str] = [
    "< {secretly }spied on @.^BHere is > report:__^E",
    "< conducted espionage in @^B and compiled/Rwrote this report^E.",
    "< gathered information/Rintelligence in @^B and wrote/Rcompiled this report^E.",
    "< {covertly }spied on @^B and gathered/Rcollected the following information:/Rintelligence^E.",
    "< used/Rutilized > {fine }covert/Rspying skills to secretly observe/Rkeep_track_of events/Rhappenings "
    "in @^B and reported the following{ information}^E.",
]


def parse_template_choices(raw_text: str) -> list[str]:
    """Parses one `.X`/`.X2` template file's raw text into its list of variant
    lines. Header line format (``RUMORS.PAS`` line ~2303:
    ``READLN(sf,choices,blockdepth)``) is ``"<choices> <blockdepth>"``,
    followed by exactly ``choices`` template lines.

    Only ``blockdepth == 1`` (a single physical line per choice) is
    supported -- every real battle-narrative template inspected for this
    phase (PLUS1-5, MINUS1-5, ZERO, WINNER, DEFWIN, RETREAT, KILLARMY,
    PURSUIT) uses ``blockdepth == 1``. A larger blockdepth needs
    ``Say_Options``'s further multi-line-per-choice handling this project
    doesn't reconstruct -- raises rather than guessing.
    """

    lines = raw_text.splitlines()
    header_parts = lines[0].split()
    choices, blockdepth = int(header_parts[0]), int(header_parts[1])
    if blockdepth != 1:
        raise NotImplementedError(
            f"multi-line template blocks (blockdepth={blockdepth}) aren't supported yet -- see module docstring"
        )
    variant_lines = lines[1 : 1 + choices]
    if len(variant_lines) != choices:
        raise ValueError(
            f"template header declares {choices} choices but only {len(variant_lines)} lines follow"
        )
    return variant_lines


def pick_variant(choices: list[str], rng: random.Random) -> str:
    """Picks one template variant uniformly at random.

    **Documented simplification**: the real engine (``RUMORS.PAS FD``)
    selects deterministically from a per-character seed (``dex``/
    ``_impcode``) threaded through a story-code bytecode log
    (``fdch``/``fdinc``/``fdcode``) this project has no equivalent for --
    see ``report/prose.py``'s own module docstring for the same category
    of gap. Picking uniformly via the caller's injectable ``rng`` is a
    reasonable stand-in that keeps rendering testable, not a recovered
    rule.
    """

    return rng.choice(choices)


# HostAK/TP/PROSE/TACTICS.X2, verbatim (mini-language intact, ^A control
# byte transcribed). See module docstring's Phase 109 addendum.
_TACTICS_TEMPLATE: dict[int, str] = {
    1: (
        "it was obvious/Rclear to all {observers }that ['s "
        "tactical/Snaval strokes_of_genius/Rbrilliance doubled_]_strength"
        "/Rguaranteed_tactical_supremacy."
    ),
    2: (
        "it soon/Rrapidly became clear/Rapparent that < was tactically "
        "outmatched/Routwitted by [.[1 maneuvered/Rutilized ] "
        "forces/Sships brilliantly/Rwith_great_sagacity."
    ),
    3: (
        "despite/Rin_spite_of > careful/Rindustrious leadership/Rplanning, "
        "< was tactically outmaneuvered/Routfoxed {by [ }and {soon }"
        "realized/Rsaw that it/Rthis_affair would_be/Rwas_becoming ^A "
        "uphill/Rdifficult struggle/Rbattle."
    ),
    4: (
        "<'s {meticulous/Rcareful }tactical plans/Rmaneuvers "
        "did_not/Rfailed_to work_out/Rsucceed{ as expected}{ against "
        "['s clever/Rprompt counterstrokes/Rremedies}, and > "
        "forces/Rmen entered_battle/Rfought with a slight/Rsmall "
        "tactical disadvantage."
    ),
    5: (
        "as the {fierce/Rdesperate }battle/Rstruggle "
        "developed/Rintensified, the tactical/Snaval wit/Rabilities of "
        "[ and < seemed/Rappeared {to be }evenly/Rwell matched{ and "
        "neither leader/Rgeneral could gain/Rachieve a tactical "
        "advantage}."
    ),
    6: (
        "in this {perilous/Snaval }chess/Rslugging match, < "
        "seemed/Rappeared to have/Rgain the tactical upper_hand/Redge."
    ),
    7: (
        "<'s wise/Rclever tactical/Snaval planning/Rmaneuvers "
        "assured/Rgave > forces/Rside ^A clear/Rundeniable "
        "advantage/Rsuperiority."
    ),
    8: (
        "< maneuvered/Rdeployed > forces/Rtroops against [ with "
        "excellent/Rgreat tactical/Sseamanship_and foresight/Rjudgement "
        "and {consequently }enjoyed/Robtained ^A important/Rtremendous "
        "tactical advantage/Rsuperiority."
    ),
    9: (
        "tactical/Snaval supremacy/Rsuperiority was {clearly }"
        "guaranteed/Rassured by <'s unmatched/Rpowerful tactical "
        "mind/Rgenius."
    ),
}


def tactical_margin_bucket(attacker_tactical_ability: int, defender_tactical_ability: int) -> int:
    """Buckets a Tactical-ability differential into the ``battac``-style
    1-9 scale ``SAY.PAS _BTac`` dispatches on (``Max(1001,Min(1009,
    1000+battac))``), 5 = even. Structurally the same documented,
    unsourced bucketing choice as ``margin_bucket()`` -- this project has
    no surviving source for ``battac``'s own formula (only the 9-value
    clamp and the confirmed, monotonic content of all 9 templates, from
    "total defender advantage" at 1 to "total attacker advantage" at 9,
    support this scale). Reuses ``turn/battle_line.py``'s own
    ``attacker_tactical_ability``/``defender_tactical_ability`` inputs
    (rulebook [7.2], already real and modeled by ``apply_tactical_
    switches``) rather than inventing a new value to bucket.
    """

    return max(1, min(9, 5 + (attacker_tactical_ability - defender_tactical_ability)))


def render_tactical_comparison(
    attacker_name: str,
    defender_name: str,
    attacker_tactical_ability: int,
    defender_tactical_ability: int,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders TACTICS.X2's sentence comparing the two sides' Tactical
    ability (``SAY.PAS _BTac``). ``is_sea`` (Phase 74) resolves the "/S"
    marker most variants carry. The "but/also" clause `_BTac` prefixes
    this with (driven by a second unconfirmed replay value, ``batluck``)
    is not reproduced here -- see module docstring.
    """

    bucket = tactical_margin_bucket(attacker_tactical_ability, defender_tactical_ability)
    values = {
        "<": attacker_name,
        "[": defender_name,
        "[1": defender_name,
        ">": f"{attacker_name}'s",
        "]": f"{defender_name}'s",
    }
    return render(_TACTICS_TEMPLATE[bucket], values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/NEMESIS.X2, verbatim, keyed by the file's own 1-based
# line number (the real dispatched ``Rint`` value has no traceable
# formula -- see module docstring's Phase 109 addendum). No render_*
# wrapper: unlike TACTICS.X2, this project cannot confirm which content
# belongs to which ``ArmyType`` nemesis pair for every entry, so no
# lookup key beyond the raw file position is asserted.
NEMESIS_TEMPLATE: dict[int, str] = {
    1: (
        "= were frightened/Rdismayed by the{ sudden/Runexpected}"
        "appearance_of/Rconfrontation_with their hated/Rdreaded nemesis."
    ),
    2: (
        "the out-matched/Rill_prepared fortifications/Rdefenses of =, "
        "were easily/Rruthlessly trampled/Rsquashed by the "
        "{lumbering/Rhumongous }Dinosaurs."
    ),
    3: (
        "the unwieldy/Rclumsy formation/Rmass of = was {severely }"
        "tested/Rshaken by the flexible/Rmaneuverable Legionnaires."
    ),
    4: (
        "the Heavy Cavalry squadrons/Rtroops bore_down_on/Rcharged = and "
        "shook_them_with/Rthey_wavered_under the initial/Rterrible "
        "shock/Rimpact."
    ),
    5: (
        "the squadrons/Rhorsemen of = found_it/Rexperienced "
        "tough_going/Ra_tough_challenge against/Rfighting the "
        "easily_defensible/Rfortress-like Chariots."
    ),
    6: (
        "the {poor/Rnervous }horses of = were frightened/Rspooked by "
        "{the howls/Rnasty_smell of }the {terrible/Rfearsome }Beasts "
        "they beheld/Rwere_faced_with."
    ),
    7: (
        "= {and their mounts }howled/Rwere_paralyzed with_fear/Rterribly "
        "when they realized/Rperceived they were_up_against/Rhad_to_fight "
        "the_dreaded/Rthose_horrible_screaming Eagles."
    ),
    8: (
        "= were staggered/Rdecimated by the arrows/Rbolts "
        "fired/Rloosed by the/Rthose pesky/Rdangerous Bowmen."
    ),
    9: (
        "= were riddled_with/Rbothered_by_the arrows_released_by/Rfire_of "
        "their dangerous/Rfeared Bowmen nemesis/Renemy."
    ),
    10: (
        "= were picked_off_one_by_one/Rrounded_up_and_slaughtered by "
        "Mermen skilled_in_the_use_of/Rarmed_with {nets/Rspearguns and "
        "}barbed/Rpoisoned harpoons."
    ),
    11: (
        "the unarmored/Runshielded soldiers/Rtroops of = were "
        "easy_targets/Rsitting_ducks for the lucky "
        "{sharp-shooting/Rrapid-firing }Bowmen."
    ),
    12: (
        "many/Rscores_of = were chopped/Rcut down/Rto_pieces by the "
        "well-armed/Rstout Axemen."
    ),
    13: (
        "the unlucky/Rterrified soldiers/Rtreants of = were "
        "terribly/Rhideously scorched/Rcharcoaled by the "
        "flameing_breath_of_the/Rfire-spitting Dragons."
    ),
    14: (
        "= found_it_tough_going/Rmet_their_match against the "
        "doughty/Rgrim Axemen, often_finding/Rtragically_unable_to_avoid"
        "_having their very/Rlong legs cut/Rchopped out_from_under_them"
        "/Rto_shreds."
    ),
    15: (
        "= roared_with_agony/Rdanced_with_pain when the "
        "Phalangites/RPhalanx_soldiers drove/Rspiked their spears/Rpikes "
        "deep/Rruthlessly into {the bellies/Rthroats of }the_Sauropods"
        "/Rthose_terrible_lizards."
    ),
}


def render_column_clash(
    column: BattleColumnResult,
    attacker_army_name: str,
    defender_army_name: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders one battle column's "<army> fought with <army> and <result>"
    sentence (``SAY.PAS _BClash`` + ``_BRes``, rulebook [7.2]'s "number of
    contests equal to the length of the battle line"). ``is_sea`` (Phase
    74) resolves the "/S" marker some ``_MARGIN_TEMPLATES`` variants carry.
    """

    opening = render("= fought/Rbattled {with }", {"=": attacker_army_name}, rng=rng)
    defender_clause = render("=", {"=": defender_army_name}, rng=rng)
    variant = pick_variant(_MARGIN_TEMPLATES[column.bres], rng)
    result_clause = render(variant, rng=rng, is_sea=is_sea)
    return f"{opening}{defender_clause} and{result_clause}"


def render_bluck_narration(
    battle_result: BattleResult,
    attacker_name: str,
    defender_name: str,
    rng: random.Random,
    *,
    province_coord: HexCoord,
    attacker_leader_id: int,
    defender_leader_id: int,
    phase: int,
) -> str:
    """Renders the whole-battle BLUCK luck-narration sentence -- real
    `BLUCK.X2`/`BLUCK2.X2` prose (Phase 584/605), keyed by `BattleResult.
    bluck_index` (drawn once per battle, Phase 370). `attacker_name`/
    `defender_name` are the two Kings, the same naming `render_battle_
    winner()` already uses; ``rng`` resolves the real template's own
    `/R` alternation.

    **Phase 605**: which of the two mutually-exclusive catalogs is used
    is not random -- `SAY.PAS`'s own real `_BLuck` dispatch (see `turn/
    battle_luck.py` module docstring) is a deterministic parity check
    over the province coordinate, the two combatant leader ids, and the
    current game phase, all four now required keyword arguments.
    """

    secondary = bluck_cluck_uses_secondary_catalog(
        province_coord.x, province_coord.y, attacker_leader_id, defender_leader_id, phase
    )
    return render_bluck_event(battle_result.bluck_index, attacker_name, defender_name, rng, secondary=secondary)


def render_cluck_narration(
    column: BattleColumnResult,
    army_name: str,
    rng: random.Random,
    *,
    province_coord: HexCoord,
    attacker_leader_id: int,
    defender_leader_id: int,
    phase: int,
) -> str | None:
    """Renders one column's local CLUCK luck-narration sentence -- real
    `CLUCK.X2`/`CLUCK2.X2` prose (Phase 584/605). Returns ``None`` when
    the column isn't "competitive" enough to be narrated at all --
    AKGEN's own confirmed `[0.4, 2.5]` pre-luck strength-ratio gate
    (`turn/battle_luck.py column_narration_eligible`); local luck still
    affects the column's own combat outcome even when it goes
    unnarrated. ``army_name`` is the column's own affected army (`=` in
    the source template) -- which side that is isn't resolved here, the
    same "caller already knows" posture `render_battle_column()` already
    takes for its own `attacker_army_name`/`defender_army_name`.

    **Phase 605 correction**: this used to append a CLUCK2 "fortune
    reversed itself" follow-up sentence after a 33% roll on indices
    `[13, 27]` -- that mechanism was built from an aggregate JSON
    statistic, not a direct `SAY.PAS` citation, and turned out to
    describe the wrong thing. `SAY.PAS`'s own real `_CLuck` dispatch
    shares `_BLuck`'s identical parity-check selector (see `turn/
    battle_luck.py` module docstring): `CLUCK.X2`/`CLUCK2.X2` are two
    mutually exclusive catalogs for the same event, not a base sentence
    plus a sometimes-appended follow-up. The four new keyword arguments
    are that formula's real inputs, the same ones `render_bluck_
    narration()` now requires.
    """

    if not column_narration_eligible(column.attacker_strength, column.defender_strength):
        return None
    secondary = bluck_cluck_uses_secondary_catalog(
        province_coord.x, province_coord.y, attacker_leader_id, defender_leader_id, phase
    )
    return render_cluck_event(column.cluck_index, army_name, rng, secondary=secondary)


def render_battle_winner(
    battle_result: BattleResult,
    attacker_name: str,
    defender_name: str,
    province_name: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str | None:
    """Renders the overall battle-winner sentence (``SAY.PAS _BWinner`` /
    WINNER.X, DEFWIN.X). Returns ``None`` for a tie -- no template exists
    for that outcome anywhere in this project's archive (see module
    docstring). ``is_sea`` (Phase 74) resolves the "/S" marker several
    WINNER.X/DEFWIN.X variants carry.
    """

    if battle_result.winner == "tie":
        return None
    if battle_result.winner == "attacker":
        variant = pick_variant(_WINNER_TEMPLATES, rng)
        values = {"<": attacker_name, "<2": attacker_name, "[": defender_name}
    else:
        variant = pick_variant(_DEFWIN_TEMPLATES, rng)
        values = {"<": attacker_name, "@": province_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


def render_destroyed_army(winner_name: str, destroyed_army_name: str, rng: random.Random) -> str:
    """Renders one destroyed-army sentence (``SAY.PAS _BDie`` / KILLARMY.X).
    ``=`` in the source template is the destroyed army, not the winner --
    KILLARMY.X's own lines have no subject of their own, appended after
    the winning side's name.
    """

    variant = pick_variant(_KILLARMY_TEMPLATES, rng)
    sentence = render(variant, {"=": destroyed_army_name}, rng=rng)
    return f"{winner_name}{sentence}"


def render_pursuit_and_destroy(pursuer_army_name: str, destroyed_army_name: str, rng: random.Random) -> str:
    """Renders a pursuit-then-destroy sentence (``SAY.PAS _BPurs`` immediately
    followed by ``_BDie`` in the same dispatch table -- PURSUIT.X's own
    lines end in "and", KILLARMY.X's lines supply the trailing leading
    space, so the two concatenate directly with no extra separator).
    """

    pursuit_clause = render(pick_variant(_PURSUIT_TEMPLATES, rng), {"=": pursuer_army_name}, rng=rng)
    kill_clause = render(pick_variant(_KILLARMY_TEMPLATES, rng), {"=": destroyed_army_name}, rng=rng)
    return f"{pursuit_clause}{kill_clause}"


def render_retreat(retreating_name: str, destination_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders a retreat sentence (RETREAT.X). ``>`` (possessive) is rendered
    as a literal ``"<name>'s"`` -- see module docstring: the real
    pronoun/possessive system stays out of scope, same as
    ``report/prose.py``'s own deferred ``<``/``[``/``>`` handling.
    ``is_sea`` (Phase 74) resolves the "/S" marker some RETREAT.X
    variants carry (e.g. "army/Sfleet").
    """

    variant = pick_variant(_RETREAT_TEMPLATES, rng)
    values = {"<": retreating_name, "^S": destination_name, ">": f"{retreating_name}'s"}
    return render(variant, values, rng=rng, is_sea=is_sea)


def render_uncontested_conquest(
    attacker_name: str, province_name: str, rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders an undefended-province conquest sentence (CONQ.X) -- a Move
    that takes an enemy province with no battle at all, distinct from
    every other function in this module (which all describe a fought
    ``BattleReport``). ``is_sea`` (Phase 74) resolves the "/S" marker 2
    of CONQ.X's 4 variants carry (e.g. "host/Sfleet").
    """

    variant = pick_variant(_CONQ_TEMPLATES, rng)
    return render(variant, {"<": attacker_name, "@": province_name}, rng=rng, is_sea=is_sea)


def render_spy_report_opening(spy_name: str, province_name: str, rng: random.Random) -> str:
    """Renders ASpy's report-opening sentence (SPY.X).

    **Phase 399 correction**: this docstring previously said "no sourced
    template exists for the rest of ``SpyReport``'s own facts (owner,
    adjacent owners, recruitable types, capital status)" -- true when
    written (Phase 63), but recruitable types (``_LSAT``,
    ``render_spy_army_type``) and capital status (``_LSCap``,
    ``render_spy_capital_province``) turned out to have real, sourced
    ``SAY.PAS`` templates after all, found and wired in Phase 115/212.
    Only **owner** and **adjacent owners** genuinely still have no
    confirmed PROSE template anywhere in the available source -- see
    module docstring's own Phase 63 addendum for the research trail
    (``RUMORS.PAS Set_Intel`` checked and ruled out; the entire ASpy
    ``Say(...)`` cluster in ``SAY.PAS`` immediately after ``_LSpy`` was
    enumerated in Phase 115 and neither fact appears in it).
    """

    variant = pick_variant(_SPY_TEMPLATES, rng)
    values = {"<": spy_name, "@": province_name, ">": f"{spy_name}'s", "^B": "", "^E": ""}
    return render(variant, values, rng=rng)


# Phase 400 -- owner and adjacent-owners are the two ASpy facts
# ``render_spy_report_opening()``'s own Phase 399 correction confirms
# have no PROSE source anywhere in the available archive. These four
# templates are **project-original**, written at the user's own direct
# request ("Vorrei che le due frasi le creassi tu") after Phase 399
# re-confirmed no source exists -- the same "data ready, no sourced
# prose" situation Trail's own [3.17] payload had before the user
# authorized project-original text for it (Phase 212, see
# ``TRAIL_TEMPER_TEMPLATE`` and neighbors below). Each fact gets both a
# present and an absent variant, matching this module's own "an empty
# result is a fact, not silence" convention (e.g. ``TRAIL_NO_TREASURES_
# TEMPLATE``) rather than skipping the line entirely.
SPY_OWNER_TEMPLATE = "@ is owned by |."
SPY_NO_OWNER_TEMPLATE = "@ is not owned by any Kingdom."
SPY_ADJACENT_OWNERS_TEMPLATE = "The provinces adjacent to @ are owned by ^L^V."
SPY_NO_ADJACENT_OWNERS_TEMPLATE = "None of the provinces adjacent to @ are owned by any Kingdom."


def render_spy_owner(province_name: str, owner_name: str | None, rng: random.Random) -> str:
    """Renders ASpy's owner line item (project-original, Phase 400 -- see
    module comment above). ``owner_name`` mirrors ``SpyReport.owner_
    kingdom_id``'s own ``None`` = unowned convention.
    """

    if owner_name is None:
        return render(SPY_NO_OWNER_TEMPLATE, {"@": province_name}, rng=rng)
    return render(SPY_OWNER_TEMPLATE, {"@": province_name, "|": owner_name}, rng=rng)


def render_spy_adjacent_owners(province_name: str, owner_names: list[str], rng: random.Random) -> str:
    """Renders ASpy's adjacent-owners line item (project-original, Phase
    400 -- see module comment above). ``owner_names`` is the list of
    distinct owning Kingdoms' display names among the spied province's
    neighbors (``SpyReport.adjacent_owners``'s own non-``None`` values,
    already resolved by the caller); empty when none of them are owned.
    """

    if not owner_names:
        return render(SPY_NO_ADJACENT_OWNERS_TEMPLATE, {"@": province_name}, rng=rng)
    return render(SPY_ADJACENT_OWNERS_TEMPLATE, {"@": province_name}, rng=rng, lists={"^V": owner_names})


# HostAK/TP/SAY.PAS _LSTax -- a single, real, hardcoded template (no
# file). See module docstring's Phase 115 addendum.
SPY_TAX_ESTIMATE_TEMPLATE = "Approximate Taxation: #"


def render_spy_tax_estimate(tax_estimate: int, rng: random.Random) -> str:
    """Renders ``_LSTax``'s line item in the ASpy report body."""

    values = {"#": str(tax_estimate)}
    return render(SPY_TAX_ESTIMATE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSAT -- a single, real, hardcoded template (no
# file). See module docstring's Phase 115 addendum.
SPY_ARMY_TYPE_TEMPLATE = "Province Army Type #: |"


def render_spy_army_type(army_type_index: int, army_type_name: str, rng: random.Random) -> str:
    """Renders ``_LSAT``'s line item in the ASpy report body.
    ``army_type_index`` reads most naturally as a 1-based index
    enumerating one of the province's possibly-multiple recruitable
    Army Types (see module docstring).
    """

    values = {"#": str(army_type_index), "|": army_type_name}
    return render(SPY_ARMY_TYPE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSList -- a single, real, hardcoded intro line (no
# file), real trailing double space kept verbatim. See module
# docstring's Phase 115 addendum.
SPY_ELEMENTS_INTRO_TEMPLATE = "the following elements are present in @:  "


def render_spy_elements_intro(province_name: str, rng: random.Random) -> str:
    """Renders ``_LSList``'s intro line for the ASpy report body's
    detail lines that follow.
    """

    values = {"@": province_name}
    return render(SPY_ELEMENTS_INTRO_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSHere -- a single, real, hardcoded template (no
# file). See module docstring's Phase 115 addendum for why ``$`` is
# left as an explicit, unresolved caller-supplied marker.
SPY_CHARACTER_HERE_TEMPLATE = "[ $ is here."


def render_spy_character_here(character_name: str, rng: random.Random, *, title: str = "") -> str:
    """Renders ``_LSHere``'s line item in the ASpy report body. ``$``
    has no confirmed ``PROSE.TXT`` meaning -- ``title`` defaults to
    ``""`` rather than guessing (see module docstring).
    """

    values = {"[": character_name, "$": title}
    return render(SPY_CHARACTER_HERE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSNone/_LSNoCh -- two single, real, hardcoded
# templates (no file). See module docstring's Phase 115 addendum.
SPY_NO_CHARACTERS_OR_FORCES_TEMPLATE = "there were no conspicuous characters or forces in @."
SPY_NO_CHARACTERS_TEMPLATE = "there were no conspicuous characters in @."


def render_spy_no_characters_or_forces(province_name: str, rng: random.Random) -> str:
    """Renders ``_LSNone``'s line item in the ASpy report body."""

    values = {"@": province_name}
    return render(SPY_NO_CHARACTERS_OR_FORCES_TEMPLATE, values, rng=rng)


def render_spy_no_characters(province_name: str, rng: random.Random) -> str:
    """Renders ``_LSNoCh``'s line item in the ASpy report body."""

    values = {"@": province_name}
    return render(SPY_NO_CHARACTERS_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSCap -- a single, real, hardcoded template (no
# file). See module docstring's Phase 115 addendum.
SPY_CAPITAL_PROVINCE_TEMPLATE = "@ is the kingdom's capital province."


def render_spy_capital_province(province_name: str, rng: random.Random) -> str:
    """Renders ``_LSCap``'s line item in the ASpy report body."""

    values = {"@": province_name}
    return render(SPY_CAPITAL_PROVINCE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSEtc -- a single, real, hardcoded closing line
# (no file). See module docstring's Phase 115 addendum.
SPY_REPORT_CLOSING_TEMPLATE = (
    "< also kept tabs on the characters in @ and any further news is "
    "in the General Intelligence Report."
)


def render_spy_report_closing(character_name: str, province_name: str, rng: random.Random) -> str:
    """Renders ``_LSEtc``'s closing line for the ASpy report body."""

    values = {"<": character_name, "@": province_name}
    return render(SPY_REPORT_CLOSING_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSLeads/_LSGarr -- both real. Deliberately left
# blocked in Phase 115 (before report/prose.py's own ^L list-insertion
# capability existed); unblocked in Phase 118 -- see module docstring's
# addendum there.
SPY_LEADS_APPROXIMATELY_TEMPLATE = "[ leads approximately ^L^V."
SPY_GARRISON_APPROXIMATELY_TEMPLATE = "there is a garrison of approximately ^L^V."


def render_spy_leads(character_name: str, army_names: list[str], rng: random.Random) -> str:
    """Renders ``_LSLeads``'s line item in the ASpy report body --
    ``army_names`` is ``PROSE.TXT``'s own ``^V`` marker ("Army name"),
    joined via ``report/prose.py``'s ``^L`` list insertion (Phase 118).
    """

    values = {"[": character_name}
    return render(SPY_LEADS_APPROXIMATELY_TEMPLATE, values, rng=rng, lists={"^V": army_names})


def render_spy_garrison(army_names: list[str], rng: random.Random) -> str:
    """Renders ``_LSGarr``'s line item in the ASpy report body --
    ``army_names`` is ``PROSE.TXT``'s own ``^V`` marker, joined via
    ``report/prose.py``'s ``^L`` list insertion (Phase 118).
    """

    return render(SPY_GARRISON_APPROXIMATELY_TEMPLATE, {}, rng=rng, lists={"^V": army_names})


def describe_aspy(
    report: SpyReport,
    *,
    spy_name: str,
    province_name: str,
    owner_name: str | None,
    adjacent_owner_names: list[str],
    rng: random.Random,
) -> list[str]:
    """Assembles ASpy's full report body from an already-computed
    ``SpyReport`` (``turn/aspy_execution.py execute_aspy()``, Phase 62,
    extended Phase 212) -- the first real assembly of the ``SAY.PAS``
    line items Phase 115/118 already built but never called from
    anywhere (``render_spy_report_opening()`` was this module's only
    real ASpy caller before this phase).

    **The assembly order below is this project's own reasoned choice,
    not a directly quoted ``REPORTS.PAS`` call sequence** -- the
    available archive gives each line item's own template
    (``SAY.PAS``'s ``CONST`` declarations, Phase 115's own docstring),
    not the surrounding ``Imp_Code`` control flow that decides which
    fire in what order. Opening sentence, then owner and adjacent
    -owners (Phase 400, project-original -- see rulebook [3.14]'s own
    "owner, owners of adjacent provinces, taxation ... army types ...
    capital" order, quoted in full in ``turn/aspy_execution.py``'s own
    module docstring), then the capital-province notice (if any), then
    the province's recruitable Army Types, then Taxation (``_LSTax``,
    Phase 253), then the characters/forces block (``_LSNone`` if
    neither characters nor forces are present; ``_LSList`` + ``_LSNoCh``
    if forces but no characters; ``_LSList`` + one ``_LSHere`` per
    spotted character (``_LSLeads`` immediately after any character who
    leads an army) + ``_LSGarr`` if there's an unled garrison), then the
    closing line.

    **Owner and adjacent-owners (Phase 400)**: ``owner_name``/
    ``adjacent_owner_names`` are already-resolved display-name strings
    -- this module never looks up ``GameState`` itself (see module
    docstring), so the caller resolves ``SpyReport.owner_kingdom_id``/
    ``adjacent_owners`` into names first (e.g. via this module's own
    ``_diplomacy_entry()``). Always rendered, present or absent, per
    ``render_spy_owner()``/``render_spy_adjacent_owners()``'s own
    "empty is a fact" convention.

    **Taxation (``_LSTax``, Phase 253)**: "Approximate Taxation: N"
    renders right after the recruitable-Army-Type lines and before the
    characters/forces block -- confirmed against the real Desktop
    sample files (e.g. `SE3__T10.K3`/`SE3__T11.K7`), where that line
    always follows the province's own ownership/adjacency narration and
    always precedes "The following elements are present..."/"There
    were no conspicuous characters or forces...". Omitted entirely when
    ``report.tax_estimate is None`` (this province's base ``tax`` was
    never recorded) -- the same "omit rather than guess" convention
    every other optional line here already follows.

    ``SpottedCharacter.estimated_alignment``/``estimated_temper``
    (Phase 139) are **not rendered here** -- ``_LSHere``'s own bare ``$``
    marker has no confirmed ``PROSE.TXT`` meaning (Phase 115's own
    docstring), so there is no sourced slot to put an alignment/temper
    guess into; that estimated data remains available on the
    ``SpyReport`` itself for a caller who wants it some other way.
    """

    lines = [render_spy_report_opening(spy_name, province_name, rng)]
    lines.append(render_spy_owner(province_name, owner_name, rng))
    lines.append(render_spy_adjacent_owners(province_name, adjacent_owner_names, rng))
    if report.is_capital:
        lines.append(render_spy_capital_province(province_name, rng))
    for index, army_type in enumerate(report.recruitable_army_types, start=1):
        lines.append(render_spy_army_type(index, ARMY_TYPE_NAME[army_type], rng))
    if report.tax_estimate is not None:
        lines.append(render_spy_tax_estimate(report.tax_estimate, rng))

    has_characters = bool(report.spotted_characters)
    has_forces = bool(report.garrison_army_names) or any(c.army_names for c in report.spotted_characters)
    if not has_characters and not has_forces:
        lines.append(render_spy_no_characters_or_forces(province_name, rng))
    else:
        lines.append(render_spy_elements_intro(province_name, rng))
        if not has_characters:
            lines.append(render_spy_no_characters(province_name, rng))
        else:
            for character in report.spotted_characters:
                lines.append(render_spy_character_here(character.name, rng))
                if character.army_names:
                    lines.append(render_spy_leads(character.name, list(character.army_names), rng))
        if report.garrison_army_names:
            lines.append(render_spy_garrison(list(report.garrison_army_names), rng))

    lines.append(render_spy_report_closing(spy_name, province_name, rng))
    return lines


def build_battle_army_names(state: GameState, battle_report: BattleReport) -> dict[int, str]:
    """Synthesizes the ``army_names`` map ``describe_battle()`` needs, via
    ``models/army_naming.py make_army_name()`` (Phase 149) -- Phase 236
    wiring, following the same precedent already established by
    ``turn/aspy_execution.py _army_display_name()`` (Phase 212) and this
    module's own ``_trail_army_name()``: despite ``make_army_name()``'s
    own docstring noting its only *directly* confirmed real Pascal call
    site is an Imperial-Office-holder display line, this project has
    already twice adopted it as the general-purpose per-army-naming
    utility for any report needing one, and battle narrative is no
    different.

    Every army id appearing anywhere in the battle -- each column's own
    front units, plus ``destroyed_army_ids``/``pursuit_destroyed_army_ids``/
    ``retreated_army_ids`` -- gets an entry. An id whose ``ArmyState``
    still exists in ``state.armies`` (not yet destroyed) uses that army's
    own real ``kingdom_id`` for race resolution, the same ``MONSTROUS_
    ARMY_RACE``-else-kingdom's-race-else-``Race.HUMAN`` rule ``_trail_
    army_name()``/``_army_display_name()`` already use. An id already
    destroyed and removed (``GameState.remove_army()`` runs during battle
    resolution, before this function ever sees the state) falls back to
    the column's own ``BattleUnit.army_type`` plus ``battle_report``'s
    own ``attacker_kingdom_id``/``defender_kingdom_id`` (Phase 231,
    stable data no destruction can remove) -- slightly less precise for
    an allied/mercenary contingent fighting under someone else's banner,
    but the only data still available for an army that's already gone.
    """

    names: dict[int, str] = {}
    for column in battle_report.battle_result.columns:
        sides = (
            (column.attacker_units, battle_report.attacker_kingdom_id),
            (column.defender_units, battle_report.defender_kingdom_id),
        )
        for units, side_kingdom_id in sides:
            for unit in units:
                if unit.source_id is None or unit.source_id in names:
                    continue
                army = state.armies.get(unit.source_id)
                if army is not None:
                    kingdom = state.kingdoms.get(army.kingdom_id) if army.kingdom_id is not None else None
                else:
                    kingdom = state.kingdoms.get(side_kingdom_id) if side_kingdom_id is not None else None
                race = MONSTROUS_ARMY_RACE.get(unit.army_type, kingdom.race if kingdom is not None else Race.HUMAN)
                names[unit.source_id] = make_army_name(unit.source_id, unit.army_type, race)
    return names


def _bluck_cluck_leader_id(commander_leader_id: int | None, kingdom_id: int | None, state: GameState) -> int | None:
    """Resolves the leader id BLUCK/CLUCK's own selector formula needs for
    one side of a battle (Phase 615) -- the battle's own commander if it
    has one, else that side's Kingdom's own King, the same fallback
    `SAY.PAS:1043 _attl:= powner[_px,_py]` uses right next to `_BLuck`'s
    own dispatch for the "no generals were present" case (`_BLList`).
    `None` if neither resolves (an unowned/kingdom-less side) -- `describe_
    battle()` skips BLUCK/CLUCK entirely rather than guessing a leader id.
    """

    if commander_leader_id is not None:
        return commander_leader_id
    if kingdom_id is None:
        return None
    king = find_king_of_kingdom(state, kingdom_id)
    return king.leader_id if king is not None else None


def describe_battle(
    battle_report: BattleReport,
    *,
    attacker_name: str,
    defender_name: str,
    province_name: str,
    state: GameState,
    destination_names: dict[int, str],
    rng: random.Random,
    is_sea: bool = False,
    phase: int | None = None,
) -> list[str]:
    """Assembles the full battle-outcome narrative from an already-computed
    ``BattleReport`` (``turn/battle_orchestrator.py fight_battle()``), in
    the same order the original dispatch table produces them: the
    whole-battle BLUCK luck sentence (Phase 615), per-column clashes each
    followed by that column's own CLUCK luck sentence (Phase 615) when
    eligible, the winner sentence, destroyed armies, pursuit kills,
    retreats, then (Phase 610) each surviving army's DECQ.X/INCQ.X
    quality-change sentence, via ``describe_quality_changes()``.

    ``army_names`` (Phase 236) is synthesized internally via
    ``build_battle_army_names(state, battle_report)`` -- see that
    function's own docstring for the sourcing and the established
    precedent (Phase 212's ``_army_display_name()``/``_trail_army_name()``)
    behind wiring ``models/army_naming.py make_army_name()`` in here.
    ``destination_names`` still maps army ids to caller-supplied display
    strings -- province-naming has no real source at all yet, so that one
    map stays caller-supplied. ``is_sea`` (Phase 74) is the caller-known
    fact of whether ``province_name`` is a Sea province, threaded to
    every sub-renderer whose own templates carry a "/S" marker.

    A battle column whose front unit(s) have no ``source_id`` at all (a
    pure combat calculation with no backing ``ArmyState``) is skipped for
    the per-column clash sentence -- not guessed.

    **Phase 615 -- BLUCK/CLUCK wiring.** `render_bluck_narration()`/
    `render_cluck_narration()` (Phase 584/605) were sourced, fully
    render-tested, and never called from anywhere until now. `SAY.PAS:
    1028-1071` -- read directly, not assumed -- confirms the real dispatch
    order this mirrors: `_BLList` (leader roster, BATLDR.X -- a separate,
    still-unwired candidate, not attempted this phase) is immediately
    followed by `_BLuck` (the whole-battle event, this function's own new
    first line), which is itself immediately followed by `_BTac`
    (tactics narration, not modeled) and then `_CLuck` (the per-column
    event) -- i.e. BLUCK is real battle-opening narration, not a closing
    remark, and CLUCK is real per-column color commentary. `phase`
    (`SAY.PAS`'s own `_rphase`) has no source for how a caller not
    already inside a phase-indexed dispatch loop would supply it, so it's
    an optional keyword-only fact (`None` default, matching `turn/
    turn_processor.py PHASE_LABELS`'s own already-established 0-4
    indexing) -- BLUCK/CLUCK are both skipped entirely (not guessed) when
    `phase` is unset, or when `battle_report.province_coord` is unset, or
    when neither a real commander nor a real King resolves for either
    side (`_bluck_cluck_leader_id()` above).
    """

    army_names = build_battle_army_names(state, battle_report)
    lines: list[str] = []

    luck_leader_ids: tuple[int, int] | None = None
    if phase is not None and battle_report.province_coord is not None:
        attacker_leader_id = _bluck_cluck_leader_id(
            battle_report.attacker_commander_leader_id, battle_report.attacker_kingdom_id, state
        )
        defender_leader_id = _bluck_cluck_leader_id(
            battle_report.defender_commander_leader_id, battle_report.defender_kingdom_id, state
        )
        if attacker_leader_id is not None and defender_leader_id is not None:
            luck_leader_ids = (attacker_leader_id, defender_leader_id)

    if luck_leader_ids is not None:
        lines.append(
            render_bluck_narration(
                battle_report.battle_result,
                attacker_name,
                defender_name,
                rng,
                province_coord=battle_report.province_coord,
                attacker_leader_id=luck_leader_ids[0],
                defender_leader_id=luck_leader_ids[1],
                phase=phase,
            )
        )

    for column in battle_report.battle_result.columns:
        if not column.attacker_units or not column.defender_units:
            continue
        attacker_army_name = army_names.get(column.attacker_units[0].source_id)
        defender_army_name = army_names.get(column.defender_units[0].source_id)
        if attacker_army_name is None or defender_army_name is None:
            continue
        lines.append(render_column_clash(column, attacker_army_name, defender_army_name, rng, is_sea=is_sea))
        if luck_leader_ids is not None:
            cluck_line = render_cluck_narration(
                column,
                attacker_army_name,
                rng,
                province_coord=battle_report.province_coord,
                attacker_leader_id=luck_leader_ids[0],
                defender_leader_id=luck_leader_ids[1],
                phase=phase,
            )
            if cluck_line is not None:
                lines.append(cluck_line)

    winner_sentence = render_battle_winner(
        battle_report.battle_result, attacker_name, defender_name, province_name, rng, is_sea=is_sea
    )
    if winner_sentence is not None:
        lines.append(winner_sentence)

    winner_name = attacker_name if battle_report.battle_result.winner == "attacker" else defender_name
    for army_id in battle_report.destroyed_army_ids:
        name = army_names.get(army_id)
        if name is not None:
            lines.append(render_destroyed_army(winner_name, name, rng))

    for army_id in battle_report.pursuit_destroyed_army_ids:
        name = army_names.get(army_id)
        if name is not None:
            # `winner_name` stands in for the specific pursuing army: report
            # .pursuit_destroyed_army_ids (battle_orchestrator._apply_pursuit)
            # only records which fleeing army got caught, not which winning
            # army did the catching -- see render_pursuit_and_destroy's
            # docstring for the underlying rulebook/data-shape reason.
            lines.append(render_pursuit_and_destroy(winner_name, name, rng))

    for army_id in battle_report.retreated_army_ids:
        name = army_names.get(army_id)
        destination = destination_names.get(army_id)
        if name is not None and destination is not None:
            lines.append(render_retreat(name, destination, rng, is_sea=is_sea))

    lines.extend(describe_quality_changes(battle_report, army_names, rng, is_sea=is_sea))

    return lines


# HostAK/TP/PROSE/MAGFEAT.X2 -- Search discovering (or not) a Magic
# Feature. See the module docstring's Phase 96 addendum for the header
# (20 choices, 1 line each) vs. the file's real 21 content lines.
_MAGFEAT_NOTHING_TEMPLATE = "< saw nothing special while scouting out the &."
_MAGFEAT_FOUND_TEMPLATE = "While scouting the &, < saw a $\\ which seemed to be of a magical nature."
_MAGFEAT_ITSELF_TEMPLATE = (
    "While scouting the &, < noticed that the & itself seems to be imbued with magical qualities."
)


def render_magic_feature_discovery(
    magic_feature: MagicFeature, province_name: str, character_name: str
) -> str:
    """Renders MAGFEAT.X2's sentence for a Search discovering (or not)
    the ``models/magic_feature.py MagicFeature`` inside ``province_name``
    (the geographic ``Feature`` being searched). No ``rng`` parameter --
    unlike every other function here, the source has no real variation
    to pick from: 19 of the 20-line choice pool are textually identical
    (see module docstring), so which one gets used never changes the
    output.

    See the module docstring's Phase 96 addendum for why the
    ``MagicFeature.POOL``-``SEALED_ENTRANCE`` case's ``$\\`` substitution
    still shows a raw, unresolved ``"Name/Falternate"``-style string.
    """

    values = {"&": province_name, "<": character_name}
    if magic_feature is MagicFeature.NONE:
        return render(_MAGFEAT_NOTHING_TEMPLATE, values)
    if magic_feature is MagicFeature.ITSELF:
        return render(_MAGFEAT_ITSELF_TEMPLATE, values)
    values["$\\"] = MAGIC_FEATURE_NAME[magic_feature]
    return render(_MAGFEAT_FOUND_TEMPLATE, values)


# Phase 616: POWMSG.X2's own real message text (`Special Features.md`
# section 9.4, user-supplied 2026-08-22) for the outcomes this phase's 9
# `TRACTABLE_POWERS` (`turn/feature_power_execution.py`) can actually
# reach. The file declares 50 record slots but only 42 are concrete text
# (the rest blank/REM) -- every id below is one of those 42, quoted
# verbatim including its own `/R` alternate-choice and `{...}` optional
# text, run through this module's own `render()` engine exactly like
# `render_magic_feature_discovery()` above. IDs for UP_SKILL/UP_APT/
# DN_SKILL/DN_APT are inferred from each message's own wording (matched
# to which ability/skill/aptitude verb it names), not independently
# confirmed against a real screenshot -- flagged here, not hidden, per
# this project's own "no source, no guess" convention. No POWMSG id
# recovered for UP_APT's own "already at the cap" case, or for MAP_FEAT/
# SAGE_DISC's own success text (only their exhaustion messages, 18/20,
# survive in the recovered 42) -- both render plain, unquoted factual
# sentences below rather than inventing flavor text the source doesn't
# supply.
_POWMSG_NEW_TEMP_ALREADY = "The $\\ turns your temper to $T.But your temper is already $T, so you're fine already."
_POWMSG_NEW_TEMP_CHANGED = (
    "You do not have the proper temperament for my liking/Rtastes!"
    "Since you have submitted to the power of the $\\, I decree that henceforth you shall be of $T temper!"
)
_POWMSG_NEW_RACE_ALREADY = "The $\\ changes characters to the $R race.But you're already $R, so you're fine already."
_POWMSG_NEW_RACE_CHANGED = (
    "You gravy-sucking/Rpathetic subhumanoid pig!"
    "I take pity on you.I shall change you to the supreme $R race.NOW, begone!"
)
_POWMSG_UP_SKILL_AT_LIMIT = (
    "The $\\ increases your skill in ^, if you have an unmodified skill less than 4."
    "But I see you have already reached that limit, so go now in peace."
)
_POWMSG_UP_SKILL_SUCCESS = "by the power of the $\\, I increase your skill in ^ by 1 skill level!"
_POWMSG_UP_SKILL_ROLL_FAILED = (
    "The $\\ increases your skill in ^, if you have sufficient aptitude."
    "But your aptitude is simply inadequate for now, so go in peace."
)
_POWMSG_UP_APT_SUCCESS = (
    "{So }you need/Rwant more aptitude in ^?Very_well/RThen, I increase/Rimprove your aptitude in ^ by 1 level!"
)
_POWMSG_DN_SKILL_AT_LIMIT = "The $\\ drains your skill in ^, but I see you have no talent for ^, so go now in peace."
_POWMSG_DN_SKILL_SUCCESS = (
    "I see you are skilled in ^, that overrated/Robnoxious disability which has caused so many problems "
    "in this_province/Rthese_parts.But I can help solve that!"
    "By the power of the $\\, you shall have 1 less skill level in ^."
)
_POWMSG_DN_APT_AT_LIMIT = (
    "The $\\ decreases your aptitude in ^, if you have an aptitude greater than 0."
    "But I see you have no aptitude for ^, so go now in peace."
)
_POWMSG_DN_APT_SUCCESS = (
    "I see you have some aptitude for ^, that overrated ability which has caused so many problems."
    "But I can help solve that!Henceforth, you shall have 1 less aptitude level in ^."
)
_POWMSG_MAP_FEAT_EXHAUSTED = "There are no more features to be told of in the provinces you have mapped."
_POWMSG_MAP_PROV_EXHAUSTED = "No more provinces exist to be told of in this world."  # POWMSG.X2 line 21, Phase 623
_POWMSG_SAGE_DISC_EXHAUSTED = "Science has come to an end!There are no more discoveries to be made in this universe."
_POWMSG_NEW_SEX_TO_FEMALE = (
    "By the power of the $\\, I change you to a woman!"
    "Hee_hee/Rho_ho, how do_you_like_THEM_apples/Rdoes_your_armor_fit_you_NOW!"
)
_POWMSG_NEW_SEX_TO_MALE = (
    "By the power of the $\\, I zap you from female to male!How do you like the_improvement/Ryour_new_organs?"
    "Har {de }har har!!!"
)

# Phase 619: POWMSG.X2 ids 21-37, the 5 Oracles/Recharge/Grant Wish/
# Gamble's own real message text (Special Features.md section 9.4,
# user-supplied 2026-08-22) -- same quoted-verbatim/`render()` pattern
# as every template above.
_POWMSG_ORAC_OFFICE_VACANT = "No one has accomplished anything in the race for this office."
_POWMSG_ORAC_GOLD_NOT_A_KING = "[ is not a King but a Hero, and has little gold to speak of."
_POWMSG_ORAC_ALIGN_SUCCESS = "[ is ^A $o character."
_POWMSG_ORAC_POWER_NO_ARMIES = (
    "[ is {perhaps/RI_think }not a general/Rmilitary_man, for/Ras [ leads/Rcommands no armies/Rsoldiers."
)
_POWMSG_ORAC_GOLD_SUCCESS = "[ has a treasury of # gold."
_POWMSG_ORAC_OFFICE_SUCCESS = "The current holder of the office of $O is [ (#), who is loyal to $K's kingdom."
_POWMSG_ORAC_TREAS_SUCCESS = "The treasure in the & is the \\."
_POWMSG_RECHARGE_SUCCESS = "The $\\ recharged the \\."
_POWMSG_GRANT_WISH_AT_LIMIT = "The $\\ cannot grant the wish if the character's skill has already reached his aptitude level."
_POWMSG_GRANT_WISH_SUCCESS = "There!<'s ^ ability is now one point higher than before!"
_POWMSG_GAMBLE_REFUSED = "Hah!The realm of $K isn't that rich.Begone!"
_POWMSG_GAMBLE_WON = (
    "< blew_on_the_dice/Rshook_the_dice_well and threw... a #.Invisible hands picked up the dice, "
    "spun/Rrolled them around the $\\ and they came up... a #!< won # gold for $K!"
)
_POWMSG_GAMBLE_LOST = (
    "< blew_on_the_dice/Rshook_the_dice_well and threw... a #.Invisible hands picked up the dice, "
    "spun/Rrolled them around the $\\ and they came up... a #.$K lost # gold."
)
_POWMSG_RECHARGE_NOT_OWNED = "Treasure # could not be recharged because < didn't own it."
_POWMSG_RECHARGE_NOT_SPELL_CASTING = "The \\ could not be recharged because it isn't a spell-casting item."
_POWMSG_DRAIN_SKILL_REFUSED = (
    "The $\\ could not be used because < didn't have enough unmodified skill levels to satisfy its thirst for wisdom."
)

# Phase 620: POWMSG.X2 id 42 -- CAST_SPELL/ANS_PRAYER's own successful
# cast (Special Features.md section 9.4, user-supplied 2026-08-22).
# FPDESC.X2 frames both powers as "grants the power to cast ~", so this
# one message is reused for both -- no separate ANS_PRAYER-only success
# id survives in the recovered 42.
_POWMSG_CAST_SPELL_SUCCESS = "I give you the power to cast a ~ spell!"


def describe_feature_power_attempt(
    outcome: FeaturePowerAttemptResult,
    rng: random.Random,
    *,
    state: GameState | None = None,
    character_name: str | None = None,
) -> str | None:
    """Renders the one POWMSG.X2 sentence for a Scout's own Feature ->
    Power [5.8] outcome, wired into `describe_search()` right after the
    Scout discovery narration. Returns `None` whenever this phase has no
    recovered POWMSG id for the specific outcome that occurred -- every
    `_apply_condition_gate()` refusal (King/alignment/gameturn/gold/
    skill-drain), UP_APT/MAP_FEAT/SAGE_DISC's own successful cases, and
    "no skill data recorded" all fall through to `None` deliberately (see
    each branch below and the module comment above these templates) --
    not a bug, `describe_search()`'s own caller already treats `None` as
    "nothing to add".

    Phase 619: the 8 SA-argument powers' own messages need to resolve
    other leaders'/kingdoms' own names, so this composer now takes
    `state`/`character_name` too (both optional, default `None`, so
    every Phase 616/617 caller/test keeps working unchanged) -- `None`
    for either makes every Phase 619 branch below render nothing rather
    than guess at a name, the same "can't resolve it, don't narrate it"
    stance as everywhere else in this composer.
    """

    values: dict[str, str] = {}
    if outcome.magic_feature is not None:
        values["$\\"] = MAGIC_FEATURE_NAME[outcome.magic_feature]
    if outcome.ability is not None:
        values["^"] = ABILITY_NAME[outcome.ability]
    if character_name is not None:
        values["<"] = character_name

    if outcome.power is Power.NEW_TEMP:
        if not outcome.applied or outcome.new_temper is None:
            return None  # refused by the condition gate -- no recovered POWMSG id for that case
        values["$T"] = TEMPER_NAME[outcome.new_temper]
        template = _POWMSG_NEW_TEMP_ALREADY if outcome.already_matched else _POWMSG_NEW_TEMP_CHANGED
        return render(template, values, rng=rng)

    if outcome.power is Power.NEW_RACE:
        if not outcome.applied or outcome.new_race is None:
            return None  # refused by the condition gate -- no recovered POWMSG id for that case
        values["$R"] = RACE_NAME[outcome.new_race]
        template = _POWMSG_NEW_RACE_ALREADY if outcome.already_matched else _POWMSG_NEW_RACE_CHANGED
        return render(template, values, rng=rng)

    # UP_SKILL/UP_APT/DN_SKILL/DN_APT's own `ability` is only ever set by
    # the real effect branch (at-limit, success, or UP_SKILL's own failed
    # roll) -- never by `_apply_condition_gate()`'s own refusals (King/
    # alignment/gameturn/gold/skill-drain) or "no skill data recorded",
    # neither of which has a recovered POWMSG id here. Checking `ability`
    # instead of `applied` alone is what tells the two kinds apart.
    if outcome.power is Power.UP_SKILL and outcome.ability is not None:
        if outcome.at_limit:
            return render(_POWMSG_UP_SKILL_AT_LIMIT, values, rng=rng)
        if outcome.applied:
            return render(_POWMSG_UP_SKILL_SUCCESS, values, rng=rng)
        return render(_POWMSG_UP_SKILL_ROLL_FAILED, values, rng=rng)

    if outcome.power is Power.UP_APT and outcome.ability is not None:
        if outcome.applied and not outcome.at_limit:
            return render(_POWMSG_UP_APT_SUCCESS, values, rng=rng)
        return None  # no recovered POWMSG id for UP_APT's own at-limit case

    if outcome.power is Power.DN_SKILL and outcome.ability is not None:
        template = _POWMSG_DN_SKILL_AT_LIMIT if outcome.at_limit else _POWMSG_DN_SKILL_SUCCESS
        return render(template, values, rng=rng)

    if outcome.power is Power.DN_APT and outcome.ability is not None:
        template = _POWMSG_DN_APT_AT_LIMIT if outcome.at_limit else _POWMSG_DN_APT_SUCCESS
        return render(template, values, rng=rng)

    if outcome.power is Power.MAP_FEAT:
        if outcome.reason == "no more features to reveal":
            return render(_POWMSG_MAP_FEAT_EXHAUSTED, values, rng=rng)
        return None  # a successful reveal has no recovered POWMSG id

    if outcome.power is Power.MAP_PROV:
        if outcome.reason == "no more provinces to reveal":
            return render(_POWMSG_MAP_PROV_EXHAUSTED, values, rng=rng)
        return None  # a successful reveal has no recovered POWMSG id

    if outcome.power is Power.SAGE_DISC:
        if outcome.reason == "no more discoveries to reveal":
            return render(_POWMSG_SAGE_DISC_EXHAUSTED, values, rng=rng)
        return None  # a successful reveal has no recovered POWMSG id

    if outcome.power is Power.NEW_SEX and outcome.applied and outcome.new_sex is not None:
        template = _POWMSG_NEW_SEX_TO_FEMALE if outcome.new_sex is Sex.FEMALE else _POWMSG_NEW_SEX_TO_MALE
        return render(template, values, rng=rng)

    # Phase 619: the 8 SA-argument powers -- every branch below needs
    # `state` to resolve another leader's/kingdom's own name; `None`
    # renders nothing rather than guess at a name (same stance as every
    # other "can't resolve it" case above).
    if outcome.power is Power.ORAC_ALIGN:
        if not outcome.applied or outcome.oracle_target_leader_id is None or outcome.oracle_alignment is None:
            return None
        if state is None:
            return None
        target = state.leaders.get(outcome.oracle_target_leader_id)
        if target is None:
            return None
        values["["] = target.name
        values["$o"] = ALIGNMENT_ABBREVIATION[outcome.oracle_alignment]
        return render(_POWMSG_ORAC_ALIGN_SUCCESS, values, rng=rng)

    if outcome.power is Power.ORAC_POWER:
        if not outcome.applied or outcome.oracle_target_leader_id is None or outcome.oracle_armies is None:
            return None
        if state is None:
            return None
        target = state.leaders.get(outcome.oracle_target_leader_id)
        if target is None:
            return None
        values["["] = target.name
        if not outcome.oracle_armies:
            return render(_POWMSG_ORAC_POWER_NO_ARMIES, values, rng=rng)
        # No recovered POWMSG id for the has-armies case (id 16 points at
        # a separate "General Intelligence Report" section this project
        # has no composer for) -- a plain, project-original factual
        # sentence instead of inventing that missing composer, same "no
        # recovered id, narrate the fact plainly" stance as MAP_FEAT/
        # SAGE_DISC's own successful reveals above.
        army_types = ", ".join(ARMY_TYPE_NAME[army.army_type] for army in outcome.oracle_armies)
        count = len(outcome.oracle_armies)
        return f"{target.name} commands {count} arm{'y' if count == 1 else 'ies'}: {army_types}."

    if outcome.power is Power.ORAC_OFFICE:
        if not outcome.applied or outcome.oracle_office is None:
            return None
        if outcome.oracle_office_holder_leader_id is None:
            return render(_POWMSG_ORAC_OFFICE_VACANT, values, rng=rng)
        if state is None:
            return None
        holder = state.leaders.get(outcome.oracle_office_holder_leader_id)
        if holder is None or holder.kingdom_id is None:
            return None
        kingdom = state.kingdoms.get(holder.kingdom_id)
        if kingdom is None:
            return None
        values["$O"] = OFFICE_NAME[outcome.oracle_office]
        values["["] = holder.name
        values["#"] = str(round(outcome.oracle_office_holder_merit_points or 0))
        values["$K"] = kingdom.name
        return render(_POWMSG_ORAC_OFFICE_SUCCESS, values, rng=rng)

    if outcome.power is Power.ORAC_GOLD:
        if outcome.oracle_target_leader_id is None or state is None:
            return None
        target = state.leaders.get(outcome.oracle_target_leader_id)
        if target is None:
            return None
        values["["] = target.name
        if not outcome.applied:
            return render(_POWMSG_ORAC_GOLD_NOT_A_KING, values, rng=rng)
        if outcome.oracle_treasury is None:
            return None
        values["#"] = str(outcome.oracle_treasury)
        return render(_POWMSG_ORAC_GOLD_SUCCESS, values, rng=rng)

    if outcome.power is Power.ORAC_TREAS:
        if not outcome.applied or outcome.oracle_feature_id is None or outcome.oracle_treasure is None:
            return None  # a real, treasure-less Feature has no recovered POWMSG id either
        if state is None:
            return None
        target_feature = state.features.get(outcome.oracle_feature_id)
        if target_feature is None:
            return None
        values["&"] = _province_label(state, target_feature.coord)
        values["\\"] = TREASURE_NAME[outcome.oracle_treasure]
        return render(_POWMSG_ORAC_TREAS_SUCCESS, values, rng=rng)

    if outcome.power is Power.RECHARGE:
        if outcome.recharged_item_id is None:
            return None
        if outcome.reason == "item not owned":
            values["#"] = str(outcome.recharged_item_id)
            return render(_POWMSG_RECHARGE_NOT_OWNED, values, rng=rng)
        if state is None:
            return None
        item = state.items.get(outcome.recharged_item_id)
        if item is None:
            return None
        values["\\"] = TREASURE_NAME[item.treasure]
        if outcome.reason == "not a spell-casting item":
            return render(_POWMSG_RECHARGE_NOT_SPELL_CASTING, values, rng=rng)
        if outcome.applied:
            return render(_POWMSG_RECHARGE_SUCCESS, values, rng=rng)
        return None

    if outcome.power is Power.GRANT_WISH:
        if outcome.reason == "insufficient skill levels":
            return render(_POWMSG_DRAIN_SKILL_REFUSED, values, rng=rng)
        if not outcome.applied or outcome.ability is None:
            return None
        if outcome.at_limit:
            return render(_POWMSG_GRANT_WISH_AT_LIMIT, values, rng=rng)
        return render(_POWMSG_GRANT_WISH_SUCCESS, values, rng=rng)

    if outcome.power is Power.GAMBLE:
        if not outcome.applied:
            if outcome.reason != "insufficient gold" or state is None or outcome.oracle_target_leader_id is None:
                return None
            leader = state.leaders.get(outcome.oracle_target_leader_id)
            if leader is None or leader.kingdom_id is None:
                return None
            kingdom = state.kingdoms.get(leader.kingdom_id)
            if kingdom is None:
                return None
            values["$K"] = kingdom.name
            return render(_POWMSG_GAMBLE_REFUSED, values, rng=rng)
        if (
            outcome.gamble_amount is None
            or outcome.gamble_character_roll is None
            or outcome.gamble_house_roll is None
            or outcome.gamble_won is None
            or outcome.oracle_target_leader_id is None
            or state is None
        ):
            return None
        leader = state.leaders.get(outcome.oracle_target_leader_id)
        if leader is None or leader.kingdom_id is None:
            return None
        kingdom = state.kingdoms.get(leader.kingdom_id)
        if kingdom is None:
            return None
        values["$K"] = kingdom.name
        # The real template repeats "#" 2-3 times for 3 distinct numbers
        # (character roll, house roll, stake) -- render()'s own `values`
        # dict substitutes one string per literal marker everywhere it
        # appears, so a positional post-pass fills each "#" left to
        # right instead (no "#" is put in `values`, so render() leaves
        # every one of them untouched -- "unrecognized symbols... are
        # left untouched," per this module's own `render()` docstring).
        template = _POWMSG_GAMBLE_WON if outcome.gamble_won else _POWMSG_GAMBLE_LOST
        text = render(template, values, rng=rng)
        text = text.replace("#", str(outcome.gamble_character_roll), 1)
        text = text.replace("#", str(outcome.gamble_house_roll), 1)
        text = text.replace("#", str(outcome.gamble_amount), 1)
        if outcome.gamble_won:
            text = text.replace("#", str(outcome.gamble_amount), 1)
        return text

    if outcome.power in (Power.CAST_SPELL, Power.ANS_PRAYER):
        if not outcome.applied or outcome.cast_spell is None:
            return None  # a failed cast (wrong terrain, ...) has no recovered POWMSG id
        values["~"] = SPELL_NAME[outcome.cast_spell]
        return render(_POWMSG_CAST_SPELL_SUCCESS, values, rng=rng)

    return None


# The 15 Spell members SPELL_CAST_ANNOUNCEMENT markers, per SPNOTE.X2's own
# real entry text (see models/enums.py's own docstring above that dict).
# Only the spells turn/cast_execution.py can actually apply are covered --
# the other 10 SPELL_CAST_ANNOUNCEMENT entries stay unconsumed here, the
# same "narrative-precedes-execution" stance already taken for Ice-Suspend
# (Phase 123) and Assassination (Phase 125): a real caller for them would
# need turn/cast_execution.py's own still-unmodeled spells built first.
_CAST_ANNOUNCEMENT_TARGET_SPELLS = frozenset(
    {Spell.KILL_ENEMY, Spell.RESURRECTION, Spell.ILLUS_ARMIES, Spell.ORATORY, Spell.CHARM, Spell.CLAIRVOYANCE}
)
_CAST_ANNOUNCEMENT_PROVINCE_SPELLS = frozenset(
    {
        Spell.PART_SEA,
        Spell.BLESS,
        Spell.EARTHQUAKE,
        Spell.FLOOD,
        Spell.TORNADO,
        Spell.PLAGUE,
        Spell.ILLUS_TERRAIN,
        Spell.HIDE_FEATURE,
    }
)
_CAST_ANNOUNCEMENT_ARMY_LIST_SPELLS = frozenset(
    {Spell.FLOOD, Spell.TORNADO, Spell.PLAGUE, Spell.SKELETAL_ARMY}
)
# Phase 193: Hide_Feature is the first spell whose own SPELL_CAST_ANNOUNCEMENT
# entry uses the "&" (Feature name) marker -- "the & in @ was magically
# hidden." No prior spell needed this marker, so there's no earlier
# precedent to follow beyond the same required/raise-if-missing pattern
# every other marker set below already uses.
_CAST_ANNOUNCEMENT_FEATURE_SPELLS = frozenset({Spell.HIDE_FEATURE})


def render_cast_announcement(
    spell: Spell,
    caster_name: str,
    rng: random.Random,
    *,
    target_name: str | None = None,
    province_name: str | None = None,
    terrain_name: str | None = None,
    army_names: list[str] | None = None,
    feature_name: str | None = None,
) -> str:
    """Renders the Cast announcement sentence for one of the 15 spells
    ``turn/cast_execution.py`` actually applies, stitching ``SAY.PAS``
    ``_LCast1``'s own opening clause (``CAST_SPELL_OPENING_COMPLETE_
    TEMPLATE``/``CAST_SPELL_OPENING_CONTINUED_TEMPLATE``, keyed by
    ``CAST_SPELL_OPENING_COMPLETE_SPELLS``) with the matching
    ``SPELL_CAST_ANNOUNCEMENT[spell]`` continuation clause -- exactly the
    "``Say(...)`` calls write sequentially with no separator" relationship
    ``models/enums.py``'s own docstring documents as the two entries'
    "apparent intended relationship," not force-verified as grammatical
    for every spell (that module's own docstring already flags
    ``CONTROL_UNDEAD``'s mid-word truncation as one confirmed case where
    it isn't). ``Spell.ORATORY`` is a second such honestly-transcribed
    oddity: its own ``SPNOTE.X2`` entry ("< cast a spell giving magical
    powers of oratory to [.") already reads as a complete sentence, yet
    ``_LCast1``'s own ``CASE`` only special-cases Tornado/Bless/Plague as
    "complete" -- so Oratory still gets the "< cast a ~ spell and "
    prefix, producing a real, redundant "cast a spell and cast a
    spell..." double statement. Transcribed as-is, not silently
    smoothed over, the same stance already taken for the Mermen
    "air-transport" wording (Phase 127) and ``_LCast1``'s own
    ``Spell.CHARM`` entry, whose leading period (".< befriended...")
    likewise concatenates into a mid-sentence full stop.

    ``target_name``/``province_name``/``terrain_name``/``army_names``/
    ``feature_name`` are each required only for the spells whose own
    announcement text actually needs them (see the four
    ``_CAST_ANNOUNCEMENT_*_SPELLS`` sets above) -- raises ``ValueError``
    naming the spell if a needed one is missing, the same fail-loud
    stance ``report/prose.py``'s own ``render()`` already takes for a
    missing ``lists`` entry.

    Works for any of the 25 ``SPELL_CAST_ANNOUNCEMENT`` entries, not
    just the 15 ``turn/cast_execution.py`` can apply -- ``describe_cast()``
    below is the only real caller, and it only ever reaches one of those
    15 (the only spells that ever produce ``applied=True``), but this
    function itself doesn't assume that narrower scope.
    """

    if spell not in SPELL_CAST_ANNOUNCEMENT:
        raise ValueError(f"no SPELL_CAST_ANNOUNCEMENT entry for {spell!r}")

    opening = (
        CAST_SPELL_OPENING_COMPLETE_TEMPLATE
        if spell in CAST_SPELL_OPENING_COMPLETE_SPELLS
        else CAST_SPELL_OPENING_CONTINUED_TEMPLATE
    )
    template = opening + SPELL_CAST_ANNOUNCEMENT[spell]

    values = {"<": caster_name, "<2": caster_name, "~": SPELL_NAME[spell]}
    lists: dict[str, list[str]] = {}

    if spell in _CAST_ANNOUNCEMENT_TARGET_SPELLS:
        if target_name is None:
            raise ValueError(f"{spell!r} needs target_name")
        values["["] = target_name
        values["[1"] = target_name
        if spell is Spell.CHARM:
            values[">"] = f"{caster_name}'s"

    if spell in _CAST_ANNOUNCEMENT_PROVINCE_SPELLS:
        if province_name is None:
            raise ValueError(f"{spell!r} needs province_name")
        values["@"] = province_name

    if spell is Spell.ILLUS_TERRAIN:
        if terrain_name is None:
            raise ValueError(f"{spell!r} needs terrain_name")
        values["`"] = terrain_name

    if spell in _CAST_ANNOUNCEMENT_ARMY_LIST_SPELLS:
        if not army_names:
            raise ValueError(f"{spell!r} needs army_names")
        lists["="] = army_names

    if spell in _CAST_ANNOUNCEMENT_FEATURE_SPELLS:
        if feature_name is None:
            raise ValueError(f"{spell!r} needs feature_name")
        values["&"] = feature_name

    return render(template, values, rng=rng, lists=lists or None)


def describe_cast(
    result: CastExecutionResult,
    *,
    caster_name: str,
    rng: random.Random,
    target_name: str | None = None,
    province_name: str | None = None,
    terrain_name: str | None = None,
    army_names: list[str] | None = None,
    feature_name: str | None = None,
) -> str | None:
    """Compose Cast's own turn-report line from an already-computed
    ``CastExecutionResult``, the same ``describe_*`` composition pattern
    ``describe_battle()``/``describe_give()``/``describe_hire()``/
    ``describe_fire()``/``describe_practice()`` already established:
    consumes the result, calls the one real sourced renderer in the
    real Pascal order, using caller-supplied display names/context (this
    project has no name-synthesis system anywhere).

    Returns ``None`` when ``result.applied`` is ``False`` -- an invalid
    target, an unsuitable province, or (``result.reason == "spell
    effect not modeled"``) one of the 10 unexecuted spells all have no
    sourced narrative and are correctly silent, mirroring ``describe_
    practice()``'s own "no narratable outcome" stance. **Correction
    (Phase 603)**: this used to also claim "a fizzled roll" belongs in
    that same silent bucket -- ``SFAIL.X`` (``render_spell_cast_
    failed()`` below) is real, sourced text for exactly that scenario,
    so the claim was wrong on its own terms. It stays unwired here for
    a different, concrete reason: every ``reason=`` string this
    module's own ``turn/cast_execution.py`` ever sets is a deterministic
    validity check (bad target, wrong terrain, not co-located, etc.) --
    grepped exhaustively, not a single call site models a probabilistic
    "the cast itself just failed" roll ``SFAIL.X``'s own text describes,
    so there is no game-state condition to gate this renderer on without
    inventing an unsourced fizzle-chance mechanic. See ``render_cast_
    announcement()`` for which of ``target_name``/``province_name``/
    ``terrain_name``/``army_names``/``feature_name`` a given spell
    actually needs.
    """

    if not result.applied:
        return None
    spell = result.request.spell
    return render_cast_announcement(
        spell,
        caster_name,
        rng,
        target_name=target_name,
        province_name=province_name,
        terrain_name=terrain_name,
        army_names=army_names,
        feature_name=feature_name,
    )


# HostAK/TP/PROSE/SAY.PAS `_LTrack` (no standalone .X/.X2 file of its own
# -- transcribed directly from the Pascal source, Phase 612) -- Kill
# Enemy's own Berserk-retaliation duel (`_execute_kill_enemy()`'s own
# Phase 310/612 addendum), the one real event `describe_cast()` above
# can never reach (`applied=False` on every branch of this outcome, so
# its own early return fires first -- see ``describe_kill_enemy_
# berserk_retaliation()`` below for the actual composer). `SAY.PAS:
# 631-632 _LTrack: Say('< went berserk over the Kill-Enemy
# attempt.Guided by eerily accurate psychotic visions, ',S_PCom);` --
# `<` is the *target* (the one whose life was attempted, who retaliates
# in a berserk rage), confirmed by `_execute_kill_enemy()`'s own
# ``_kill_enemy_combatant(state, target, temper=Temper.BERSERK)`` call,
# not the caster. The missing space after "attempt." is a real,
# verbatim quirk (the same "ago.It"-style run-on this project already
# knows to preserve, not a transcription error).
#
# The neighboring `_LBers`/`_LKillE` constants (`SAY.PAS:629-630`) are
# deliberately NOT used here: `_LKillE` ("< cast a ~ spell and , and
# destroyed/slew [ with > powerful/dark magic") reads as the tail of
# `_LCast1`'s *successful*-cast opening ("< cast a ~ spell and "), i.e.
# a different, unrelated dispatch chain for an instant-kill outcome
# this project doesn't model (Kill_Enemy's own success is coma, per
# `_execute_kill_enemy()`'s own Phase 310 docstring point 3) -- not
# part of the failed-roll Berserk branch at all. `_LBers` ("[ flew into
# a berserk rage and fought with increased strength.") sits right next
# to `_LTrack` and plausibly continues its own dangling ", " -- but
# without the original dispatch/calling code (not preserved in this
# project's own Pascal archive, only `SAY.PAS`/`RUMORS.PAS` survive),
# there's no way to confirm that chain rather than guess it, so this
# project transcribes only `_LTrack` itself and does not use `_LBers`.
_KILL_ENEMY_BERSERK_ONSET_TEMPLATE = (
    "< went berserk over the Kill-Enemy attempt.Guided by eerily accurate psychotic visions, "
)


def render_kill_enemy_berserk_onset(target_name: str) -> str:
    """Renders `_LTrack`'s own opening fragment for the Berserk-
    retaliation duel (Phase 612) -- see the module comment above for
    the sourcing and why `_LBers`/`_LKillE` aren't used. No `rng`
    parameter: the real text has no `/R`/`{}` choice markers of its
    own, the same "nothing to vary" shape ``render_magic_feature_
    discovery()`` already established.

    Deliberately NOT terminated with a period -- the real source ends
    on a dangling ", " (mid-sentence, meant to concatenate directly
    into whatever `Say()` call follows in the original engine).
    ``describe_kill_enemy_berserk_retaliation()`` concatenates this
    string directly onto its own first rendered swing sentence, the
    same "`Say()` calls write sequentially with no separator, even
    when that reads awkwardly" precedent ``render_cast_announcement()``
    already established (and already preserves, e.g. `CONTROL_UNDEAD`'s
    mid-word truncation) rather than smoothing the join over.
    """

    return render(_KILL_ENEMY_BERSERK_ONSET_TEMPLATE, {"<": target_name})


def describe_kill_enemy_berserk_retaliation(
    result: CastExecutionResult, *, caster_name: str, target_name: str, rng: random.Random
) -> list[str]:
    """Assembles the Berserk-retaliation duel's own narration (Phase
    612) from an already-computed ``CastExecutionResult`` -- the
    ``result.applied is False`` outcome ``describe_cast()`` above can
    never narrate on its own, so ``describe_turn_results()``'s own
    ``ActionCode.CAST`` branch calls this as a second, independent
    composer on the very same result, mirroring how its own
    ``ActionCode.PURSUE`` branch already calls ``describe_pursue()``
    (one line) then extends with ``describe_encounter_combat()`` (a
    list) from the same underlying result.

    Returns ``[]`` when ``result.kill_enemy_berserk_winner is None`` --
    covers every ordinary Cast outcome (no Berserk duel at all) *and*
    the vanishingly rare ``max_rounds``-exhausted draw, which has no
    sourced sentence of its own either way.

    Order: `_LTrack`'s own opening fragment, concatenated directly
    (no space) onto the first ``result.melee_swings`` entry's own
    rendered sentence -- see ``render_kill_enemy_berserk_onset()``'s
    own docstring for why. Every further swing (``render_melee_
    attack()``/``render_attack_hit()``/``render_attack_missed()``, the
    same triplet ``describe_encounter_combat()``/``describe_search()``
    already use) follows as its own line, in chronological
    (``result.melee_swings``) order, then ``render_mortally_wounded()``
    (MORTWOUN.X) and ``render_character_death()`` (HORDEATH.X, Phase
    611) for whichever side lost. ``"a"`` = the caster, ``"b"`` = the
    target, matching ``CastExecutionResult.melee_swings``'s own Phase
    612 docstring.
    """

    if result.kill_enemy_berserk_winner is None:
        return []

    onset = render_kill_enemy_berserk_onset(target_name)
    swing_lines: list[str] = []
    for swing in result.melee_swings:
        attacker_name, defender_name = (caster_name, target_name) if swing.attacker == "a" else (target_name, caster_name)
        attack_line = render_melee_attack(attacker_name, defender_name, _MELEE_ATTACK_METHOD, rng)
        attack_line += (
            render_attack_hit(defender_name, swing.damage, rng)
            if swing.hit
            else render_attack_missed(attacker_name, defender_name, "blade", rng)
        )
        swing_lines.append(attack_line)

    lines: list[str] = []
    if swing_lines:
        swing_lines[0] = onset + swing_lines[0]
        lines.extend(swing_lines)
    else:
        # Defensive only -- resolve_melee_duel() always produces at
        # least one swing before a duel can have a real winner.
        lines.append(onset)

    loser_name = target_name if result.kill_enemy_berserk_winner == "a" else caster_name
    lines.append(render_mortally_wounded(loser_name, rng))
    lines.append(render_character_death(loser_name, rng))
    return lines


# HostAK/TP/PROSE/SFAIL.X, SBUNGLE.X -- a Cast that just fizzles, no
# validity reason involved (Phase 603). `SAY.PAS:895 _SFail: FD('sfail',
# S_Priv,0)` is the ordinary Cast Spell action's own sibling ("S" =
# Spell -- `S_Priv` severity, the same context ``describe_cast()``
# itself operates in); `SAY.PAS:674 _LBung: FD('sbungle',S_PCom,8)` is
# the personal-combat Cast tactic's own sibling (`S_PCom`, the same
# family Phase 588's `CCAST.X`/`FLAMEREL.X`/`SHADTR.X` cluster lives
# in). Neither is wired -- see ``describe_cast()``'s own Phase 603
# correction above for why ``SFAIL.X`` stays unwired despite being real,
# sourced text; ``SBUNGLE.X`` has the identical problem one level down,
# since this project's combat resolution has no probabilistic
# spell-fizzle roll of its own either. ``~`` is the already-established
# spell-name marker (``render_cast_no_treasure()``, Phase 588).
_SBUNGLE_TEMPLATES: list[str] = [
    "< attempted to bolster/Rhelp > fortunes/Rcause with ^A ~ "
    "spell, but it fizzled/Rsputtered at the last moment/Rsecond.",
    "< thought to attempt/Rcast ^A ~ spell, but "
    "dropped/Rcouldn't_find ^A crucial/Rneeded material component "
    "before < could make > spellcast/Rattempt.",
    "< waved/Rraised > arms/Rhands{ and gestured "
    "mightily/Rrhythmically}, intending/Rmeaning to cast ^A ~ "
    "spell, but it backfired/Rwent_awry and ^A rabbit/Rdove "
    "popped/Rtumbled out of > sleeve/Rhat instead.",
    "< incanted/Rchanted the magic word{s} for ^A ~ spell, but "
    "bit > lip/Rtongue {on the last utterance/Rsyllable }and "
    "flubbed/Rbotched the spell.",
]


def render_spell_fizzled_in_combat(character_name: str, spell_name: str, rng: random.Random) -> str:
    """Renders SBUNGLE.X's sentence for a personal-combat Cast that just
    fizzles, no validity reason involved (Phase 603).
    """

    variant = pick_variant(_SBUNGLE_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s", "~": spell_name}
    return render(variant, values, rng=rng)


_SFAIL_TEMPLATES: list[str] = [
    "< attempted/Rtried ^A ~ spell, but bungled/Rbotched it.",
    "< failed in > {ineffectual }attempt to cast ^A ~ spell.",
    "<'s attempted cast of the ~ spell was_unsuccessful/Rdidn't_work.",
    "<'s ~ spell backfired/Rfizzled and < wound_up/Rwas_left "
    "{with > face }covered with psycho-kinetic slime/Rgoo.",
]


def render_spell_cast_failed(character_name: str, spell_name: str, rng: random.Random) -> str:
    """Renders SFAIL.X's sentence for an ordinary Cast Spell action that
    just fizzles, no validity reason involved (Phase 603) -- the
    non-combat sibling of ``render_spell_fizzled_in_combat()``.
    """

    variant = pick_variant(_SFAIL_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s", "~": spell_name}
    return render(variant, values, rng=rng)


# **Project-original, not sourced from SAY.PAS/RUMORS.PAS** (Phase 148):
# the skill-book-read moment (see ``describe_use_mi()``'s own docstring
# for the full research trail confirming no real template exists
# anywhere in the archive). Added on the user's own explicit request and
# exact wording ("<character> legge il <book> e la sua abilità aumenta
# di un livello!") after that research came back empty, the same
# "explicitly documented as an unsourced design choice" convention this
# project's own standing instructions require whenever a gap is filled
# without a source -- unlike every other template in this module, this
# one is *not* a transcription of anything in ``HostAK/TP/PROSE/``.
SKILL_BOOK_READ_TEMPLATE = "< read the \\ and > ^ increased by one level!"


def render_skill_book_read(character_name: str, book_name: str, ability_name: str, rng: random.Random) -> str:
    """Renders the project-original skill-book-read sentence -- see
    ``SKILL_BOOK_READ_TEMPLATE``'s own comment for why this one isn't a
    real ``SAY.PAS``/``RUMORS.PAS`` transcription. ``book_name`` is
    ``PROSE.TXT``'s own ``\\`` (Magic Item) marker; ``ability_name`` is
    its own ``^`` (Ability name) marker, the same two markers
    ``render_item_give()``/``render_practice_tutored()`` already use.
    """

    values = {"<": character_name, ">": f"{character_name}'s", "\\": book_name, "^": ability_name}
    return render(SKILL_BOOK_READ_TEMPLATE, values, rng=rng)


def describe_use_mi(
    result: UseMIExecutionResult,
    *,
    caster_name: str,
    rng: random.Random,
    target_name: str | None = None,
    province_name: str | None = None,
    terrain_name: str | None = None,
    army_names: list[str] | None = None,
    book_name: str | None = None,
    ability_name: str | None = None,
) -> str | None:
    """Compose Use_MI's own turn-report line from an already-computed
    ``UseMIExecutionResult`` (Phase 141), fifth slice of the
    report-assembler thread.

    Wand use (``result.cast_result is not None``) is, per rulebook
    [3.11] and ``turn/use_mi_execution.py``'s own docstring, a real Cast
    under the hood -- so this just delegates straight to
    ``describe_cast()``, the same sourced ``SPELL_CAST_ANNOUNCEMENT``
    narrative a top-level Cast order gets (``wand_skill_level``, Phase
    141, only changes the *mechanics*, not which sentence is rendered).

    Skill-book use (``result.ability_boosted is not None``): Phase 146's
    own research confirmed no real source exists for this moment.
    `TREASAB.X2`'s own book labels (e.g. "+1 Melee when read",
    ``models/treasure.py TREASURE_LABEL``) are terse inventory text, not
    a turn narrative; `TREASURE.X2`'s per-book flavor text is dispatched
    by `SAY.PAS Desc_Treas`/`_TrDesc` only from `REPORTS.PAS List_Treas`'s
    own per-leader inventory listing (gated on a waiting/new king
    browsing their kingdom), never from a Use_MI action; and `_TrDust`
    (`RUMORS.PAS` story code 5001, "it crumbled to dust...", the one
    candidate that *would* fit a "used up its last charge" moment) has
    no real emission site anywhere in the archive -- an orphaned
    constant, not a live narrative path. Phase 148, on the user's own
    explicit request, fills this confirmed gap with
    ``render_skill_book_read()``, a **project-original** sentence (see
    ``SKILL_BOOK_READ_TEMPLATE``'s own comment) -- rendered only when
    the caller supplies both ``book_name`` and ``ability_name``; without
    either, this still renders nothing (the same "caller supplies what
    state can't determine" convention every other composer here already
    follows, e.g. ``describe_give()``'s own ``item_name``).

    Every other case (``result.applied is False``: item not found, not
    owned, or not a Use_MI target) also renders nothing.
    """

    if result.cast_result is not None:
        return describe_cast(
            result.cast_result,
            caster_name=caster_name,
            rng=rng,
            target_name=target_name,
            province_name=province_name,
            terrain_name=terrain_name,
            army_names=army_names,
        )
    if result.ability_boosted is not None and book_name is not None and ability_name is not None:
        return render_skill_book_read(caster_name, book_name, ability_name, rng)
    return None


# HostAK/TP/PROSE/EXPMOVE.X -- the Explore action's own progress report.
# See module docstring's Phase 110 addendum.
_EXPMOVE_TEMPLATES: list[str] = [
    "< explored @^B {well }and now #% of it has been explored^E.",
    "< travelled/Ssailed throughout/Rabout @, exploring its "
    "features/SIslands.^BAfter > {exploration }efforts, #% of it has "
    "been explored to date.^E",
    "< roamed/Scruised through/Raround_in @, exploring the "
    "terrain/Schannels there^B, and now #% of it has been explored^E.",
    "< explored @, taking careful/Rprecise notes of the "
    "terrain/Sislands and features^B, and now #% of it has been "
    "explored^E.",
    "< wandered/Scruised freely/Rfar_and_wide in/Rabout @, "
    "exploring/Runcovering its secrets/Rmysteries^B, and raising our "
    "exploration level in @ to #%^E.",
    "< explored/Snavigated @ carefully/Rthoroughly, leaving no "
    "stone_unturned/Sisland_uncharted^B, and our exploration level "
    "there has risen to #%^E.",
]


def render_explore_progress(
    character_name: str,
    province_name: str,
    new_percent: int,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders EXPMOVE.X's sentence for a dedicated Explore action
    (rulebook Explore, ``turn/exploration.py resolve_explore()``'s own
    ``ExploreResult.new_percent``). ``is_sea`` (Phase 74) resolves the
    "/S" marker most variants carry. The ``^B``/``^E`` King-exclusion
    span (see module docstring) is stripped, not resolved.
    """

    variant = pick_variant(_EXPMOVE_TEMPLATES, rng)
    values = {
        "<": character_name,
        "@": province_name,
        "#": str(new_percent),
        ">": f"{character_name}'s",
        "^B": "",
        "^E": "",
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/COEXP.X -- exploration gained as a side effect of a
# Move. See module docstring's Phase 110 addendum.
_COEXP_TEMPLATES: list[str] = [
    "< observed the area/Rterrain while we were on_the_march/S"
    "cruising_forward^B and now #% of @ has been explored^E.",
    "< found some time to explore/Rinvestigate @ while "
    "marching/Ssailing_ahead.^B#% of it has been explored to date.^E",
    "< marched_along/Snavigated some previously/Rheretofore "
    "unexplored paths/Schannels^B, raising our exploration knowledge "
    "to #%^E.",
    "while on_the_march/Son_the_move, < took ^A interest in the "
    "terrain/Sislands of @, exploring some unknown areas/Rterritory."
    "^BWe have now explored #% of @^E.",
    "< made some side trips while marching/Ssailing through @^B and "
    "now #% of @ has been explored^E.",
    "< marched/Ssailed along ^A unusual/Runconventional "
    "route/Scourse through @^B and raised our {level of }exploration "
    "there to #%^E.",
]


def render_explore_continued(
    character_name: str,
    province_name: str,
    new_percent: int,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders COEXP.X's sentence for exploration gained as a side
    effect of a Move (``turn/move_execution.py``'s own already-modeled
    partial-exploration side effect, Phase 3). ``is_sea`` (Phase 74)
    resolves the "/S" marker most variants carry.
    """

    variant = pick_variant(_COEXP_TEMPLATES, rng)
    values = {
        "<": character_name,
        "@": province_name,
        "#": str(new_percent),
        ">": f"{character_name}'s",
        "^B": "",
        "^E": "",
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/SAY.PAS _LExpMax -- a single, real, hardcoded template (no
# file). See module docstring's Phase 110 addendum.
EXPLORE_ALREADY_MAXED_TEMPLATE = (
    "< tried to explore @ but it seemed that it had already been "
    "completely explored."
)


def render_explore_already_maxed(character_name: str, province_name: str, rng: random.Random) -> str:
    """Renders ``_LExpMax``'s sentence for an Explore that found nothing
    left to explore (``ExploreResult.fully_explored`` already ``True``
    before this Explore ran).
    """

    values = {"<": character_name, "@": province_name}
    return render(EXPLORE_ALREADY_MAXED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LExpDiff -- a single, real, hardcoded precursor
# clause (no trailing period -- the caller concatenates one of the three
# templates above). See module docstring's Phase 110 addendum.
EXPLORE_NOT_PRESENT_PREFIX = "< wasn't in @ so "


# HostAK/TP/PROSE/GOBOW.X -- closing to bow range before a Fire Arrow
# attack. See module docstring's Phase 111 addendum.
_GOBOW_TEMPLATES: list[str] = [
    "< {quickly/Rspeedily }moved {in}to bow range.",
    "< loped/Sswam along smoothly/Rsteadily{, conserving > energy,} "
    "and closed to bow range.",
    "< {menacingly/Rcautiously }advanced to bow range.",
]


def render_move_to_bow_range(character_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders GOBOW.X's sentence for closing to bow range before a Fire
    Arrow attack (``turn/encounter.py``'s already-modeled combat, Phase
    48). ``is_sea`` (Phase 74) resolves the "/S" marker one variant carries.
    """

    variant = pick_variant(_GOBOW_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s"}
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/GOMEL.X -- closing to melee range. See module
# docstring's Phase 111 addendum (requested for symmetry with GOBOW.X;
# the Melee attack action itself, SWANGAT.X, is left for a follow-up).
_GOMEL_TEMPLATES: list[str] = [
    "< charged/Sdarted into the_melee/Rmelee_range.",
    "< rushed/Sswam {eagerly/Rlustily }into melee combat.",
    "< closed to melee range, seething/Rfilled with "
    "{uncontrolled/Rmaniacal }blood-lust.",
]


def render_move_to_melee_range(character_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders GOMEL.X's sentence for closing to melee range. ``is_sea``
    (Phase 74) resolves the "/S" marker two variants carry.
    """

    variant = pick_variant(_GOMEL_TEMPLATES, rng)
    values = {"<": character_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/FARR.X -- the Fire Arrow attack action itself. See
# module docstring's Phase 111 addendum.
_FARR_TEMPLATES: list[str] = [
    "< {boldly }$S ^A ^W at [",
    "< $S ^A {angry }^W at [",
    "drawing back{ with all > strength}, < $S ^A ^W at [",
    "< took {careful }aim and $S ^A ^W at [",
    "< $S ^A hard/Rpowerful ^W at [",
    "with steady/Runwavering strength, < readied ^A ^W and $S it at [",
]


def render_fire_arrow_attack(character_name: str, opponent_name: str, rng: random.Random) -> str:
    """Renders FARR.X's sentence for the Fire Arrow attack action itself
    -- no trailing punctuation, meant to be immediately followed by
    ``render_attack_missed()`` (or a future hit/mortal-wound
    continuation) to form one complete sentence.
    """

    variant = pick_variant(_FARR_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": opponent_name,
        ">": f"{character_name}'s",
        "$S": "Fired",
        "^W": "arrow",
    }
    return render(variant, values, rng=rng)


# HostAK/TP/SAY.PAS _LSquee (Phase 413) -- Hand of Death's own per-round
# attack-action clause, the same FARR.X-shaped role ``render_fire_arrow_
# attack()`` plays for Fire Arrow, immediately followed by
# ``render_attack_hit()`` to form one complete sentence (Hand of Death's
# own attack always lands -- see ``turn/encounter.py resolve_hand_of_
# death_channel()``'s own docstring -- so, unlike Fire Arrow, there is no
# miss continuation to choose between). **Never transcribed from the
# original source** (`_LSquee: FD2('squeeze',S_PCom,5)` names 5 real
# templates and nothing else survives in the available archive) --
# reconstructed instead from real per-round Hand of Death narration
# across 8 independent turn-report files (`SE3__T1.K9`, `SE3__T2.K9`,
# `SE3__T7.K8`, `SE3__T8.K1/K4/K5/K8`, `SE3__T10.K7/K8/K9`,
# `SE3__T11.K9`), each line ending in the same shared ANDINFL.X
# continuation this project already models (`render_attack_hit()`) --
# confirmed by the user's own direct play experience to be Hand of
# Death's own output, not a separate mechanic. The opening "began making
# squeezing motions" line seen in the same files is a different, already
# -modeled template (`SPELL_CAST_ANNOUNCEMENT[Spell.HAND_OF_DEATH]`,
# Phase 122) -- not one of these 5.
#
# **Phase 414 correction**: this project's Pascal source turned out to
# still be reachable (just not at the path Phase 413 searched). Re-
# checked `_LSquee` directly against it: `CTME.PAS`'s `Death` enum
# (`Squeeze,Batter,Crush,Slash,...`) is a per-weapon damage-narration
# category, not a spell-specific one -- `weapkill[Tentacles] = Squeeze`,
# and Giant Octopus (`mtweap1`'s sole `Tentacles`-armed monster) is the
# category's own formally-declared owner, not Hand of Death. `_LSquee`'s
# real *caller* -- the code deciding when it actually fires, and whether
# Hand of Death's own attack narration routes through the same category
# -- is still missing from the 13 surviving `.PAS` files, the same
# "declared, caller lost" gap this project already documents elsewhere
# (`Tax_Base`, `ACost`/`LCost`). No real Giant Octopus combat log exists
# in this project's own sample turn-report files to test the alternate
# reading against -- every sampled encounter with it either fled or
# never reached combat. The wiring below is kept exactly as Phase 413
# built it: the user's own direct play experience is its real basis,
# not this newer, more precisely-sourced-but-still-inconclusive Pascal
# citation.
#
# **Phase 631 -- closed for good.** The user directly reconfirmed this
# reading ("lo squeeze e' il prose dello spell Hand of Death") this
# phase. `CTME.PAS`'s `Death` enum and `CTBOTH.PAS`'s `maneuver` enum
# both naming "Squeeze" are the same underlying narration concept, not
# competing theories -- Hand of Death borrows Giant Octopus's own
# natural-weapon damage-narration category to narrate its own spell
# attack. See `turn/encounter.py resolve_hand_of_death_channel()`'s own
# Phase 631 addendum for the full account, including why `Maneuver.
# SQUEEZE` was also confirmed to not be a real, separately-wireable
# player Search tactic (a question raised independently the same phase).
_SQUEEZE_TEMPLATES: list[str] = [
    "< curled/Rwrapped > phantasmal hand around ['s heart and squeezed it{ viciously/Rmercilessly}",
    "< curled/Rwrapped > phantasmal hand around ['s liver and squeezed it{ viciously/Rmercilessly}",
    "< clenched > fist{ tightly}, squeezing the innards of [",
    "< clenched > fist, squeezing the intestines of [",
    "< brought > hands together and yanked/Rpulled them apart in a ripping/Rtearing gesture/Rmotion, "
    "provoking a{ terrible/Rblood-curdling} squeal{ of pain} from [",
]


def render_squeeze_attack(character_name: str, opponent_name: str, rng: random.Random) -> str:
    """Renders ``_LSquee``'s sentence for Hand of Death's own per-round
    squeeze -- no trailing punctuation, meant to be immediately followed
    by ``render_attack_hit()`` (Hand of Death's own attack always lands,
    so ``render_attack_missed()`` never applies here) to form one
    complete sentence, the same shape ``render_fire_arrow_attack()``
    established.
    """

    variant = pick_variant(_SQUEEZE_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": opponent_name,
        ">": f"{character_name}'s",
    }
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/ANDMISS.X -- the miss continuation clause, shared by
# every attack-action sentence (Fire Arrow's FARR.X here; Melee's
# SWANGAT.X in a future phase). See module docstring's Phase 111
# addendum.
_ANDMISS_TEMPLATES: list[str] = [
    " and missed{ by_a_mile/Rbadly}.",
    " but [1 dodged/Revaded the blow/R^W.",
    " but > ^W whiffed/Sdarted {harmlessly }through the air/Smurky_water.",
    " but > aim was just/Rslightly off{ the mark}.",
    " and would have struck/Rhit [ if [1 hadn't ducked/Rsidestepped"
    "{ just then}.",
]


def render_attack_missed(
    attacker_name: str,
    defender_name: str,
    weapon: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders ANDMISS.X's continuation clause for a missed attack --
    concatenate directly after ``render_fire_arrow_attack()`` (or a
    future Melee attack-action renderer). ``weapon`` is ``PROSE.TXT``'s
    own ``^W`` marker ("Striking weapon"), matching whichever weapon the
    preceding attack-action sentence named (e.g. ``"arrow"``). ``is_sea``
    (Phase 74) resolves the "/S" marker one variant carries.
    """

    variant = pick_variant(_ANDMISS_TEMPLATES, rng)
    values = {
        "[": defender_name,
        "[1": defender_name,
        ">": f"{attacker_name}'s",
        "^W": weapon,
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/ANDINFL.X -- the hit continuation clause, parallel to
# ANDMISS.X's own miss clause. See module docstring's Phase 112 addendum.
_ANDINFL_TEMPLATES: list[str] = [
    " and inflicted # damage points.",
    " and scorched/Rwalloped [ with # damage points.",
    " and damaged [, scoring/Rinflicting # damage points.",
    " and scored on [, inflicting/Rdoing # points of damage.",
    " and scored/Rinflicted # damage points on [.",
]


def render_attack_hit(defender_name: str, damage_points: int, rng: random.Random) -> str:
    """Renders ANDINFL.X's continuation clause for a successful hit --
    concatenate directly after ``render_fire_arrow_attack()`` (or a
    future Melee attack-action renderer). ``damage_points`` is
    ``PROSE.TXT``'s own ``#`` marker, matching ``turn/encounter.py
    roll_fire_arrow_attack()``'s own already-modeled return value.
    """

    variant = pick_variant(_ANDINFL_TEMPLATES, rng)
    values = {"[": defender_name, "#": str(damage_points)}
    return render(variant, values, rng=rng)


# HostAK/TP/SAY.PAS _LDevast -- a single, real, hardcoded template (no
# file). See module docstring's Phase 112 addendum for the honest
# discrepancy between this code's dispatched content and its own
# declared RUMORS.PAS constant value.
ATTACK_DEVASTATING_HIT_TEMPLATE = " and devastated/Rannihilated [."


def render_attack_devastating_hit(defender_name: str, rng: random.Random) -> str:
    """Renders ``_LDevast``'s continuation clause for a devastating/
    lethal hit -- concatenate directly after ``render_fire_arrow_attack()``
    the same way ``render_attack_hit()`` does. This project has no
    source for what distinguishes an ordinary hit (``_LInfl``) from a
    devastating one (``_LDevast``) -- the caller decides which to call.
    """

    values = {"[": defender_name}
    return render(ATTACK_DEVASTATING_HIT_TEMPLATE, values, rng=rng)


# HostAK/TP/PROSE/MORTWOUN.X -- a standalone sentence marking the
# defender's fate, appended *after* the attack+hit sentence rather than
# concatenated onto it. See module docstring's Phase 112 addendum.
_MORTWOUN_TEMPLATES: list[str] = [
    "[1 was mortally/Rfatally wounded.",
    "[1 fell/Ssank_down, fatally/Rmortally injured.",
    "[1 dropped/Ssank to the ground/Sbottom, fatally/Rmortally pierced.",
    "[1 staggered/Sflailed_about, stunned by {the force of }the "
    "deadly/Rmortal blow.",
]


def render_mortally_wounded(defender_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders MORTWOUN.X's standalone sentence marking the defender's
    fate after a lethal hit. ``is_sea`` (Phase 74) resolves the "/S"
    marker two variants carry. Note the 4th variant describes a stun,
    not a fatal wound, despite the file's own name (see module
    docstring).
    """

    variant = pick_variant(_MORTWOUN_TEMPLATES, rng)
    values = {"[1": defender_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/HORDEATH.X -- a generic character-death closing
# sentence (Phase 607), distinct from MORTWOUN.X above: `SAY.PAS:429-432
# _LDies: BEGIN t:= Rint; FD('hordeath',Min(S_Comm,event_lev+1),6{1001+
# Rint}); END` sits between `_LWDie`/`_LSick` (a near-death coma) and
# `_LSucc` (succession), not inside the S_PCom personal-combat cluster
# MORTWOUN.X/SWANGAT.X live in -- its own severity is computed from a
# caller-supplied `event_lev`, suggesting it's the shared final beat for
# *any* character death (combat, disease, assassination, etc.), not a
# combat-specific one. `t:= Rint` and the third `FD` argument (a fixed
# `6`, with `{1001+Rint}` a Pascal *comment* showing an alternate,
# unused expression) don't affect which of this file's own 2 real
# choices gets picked -- every other transcribed catalog's own such
# argument has likewise never needed interpreting by this project's
# `pick_variant()`-based rendering. Also confirmed aliased as `F9.X2`
# (`RUMORS.PAS`'s own `F`+digit `Say` indirection, byte-identical
# payload). Wired as of Phase 611 into the 3 real personal-combat-death
# call sites this project's own `GameState.remove_leader()` chokepoint
# reaches from a live composer -- `describe_encounter_combat()`
# (Challenge/Pursue's shared duel narration) and `describe_search()`
# (a guardian-monster win) -- each already appends `render_mortally_
# wounded()` right where the death is confirmed, so this generic
# trailer follows immediately after, matching `_LDies`'s own dispatch
# position right after the cause-specific sentence. **Phase 612**: also
# wired into the new `describe_kill_enemy_berserk_retaliation()`
# (Kill Enemy's own Berserk-retaliation duel, `turn/cast_execution.py`)
# -- `describe_cast()` itself still can't reach this outcome
# (`applied` stays False on every branch), but `describe_turn_
# results()`'s own `ActionCode.CAST` branch now calls the new composer
# as a second, independent pass over the same result, the same "two
# composers, one result" shape Pursue's own `describe_pursue()` +
# `describe_encounter_combat()` pairing already established. One real
# `remove_leader()` call site remains genuinely unreached by any
# composer: `turn/assassin_guild.py`'s Grandfather of Assassins
# resolver isn't called from production code at all yet -- wiring it
# needs building a new narration path from scratch once (if ever) the
# resolver itself gets a real caller, left for a future phase.
_HORDEATH_TEMPLATES: list[str] = [
    "and so it was/Rcame_to_pass that < met > unseemly/Rtragic end.",
    "thus did < {finally }die, ^A brave_end/Rdefiant_death by any standard.",
]


def render_character_death(character_name: str, rng: random.Random) -> str:
    """Renders HORDEATH.X's generic character-death closing sentence
    (Phase 607). Wired as of Phase 611 into ``describe_encounter_
    combat()``/``describe_search()``, right after their own ``render_
    mortally_wounded()`` call -- see the module comment above.
    """

    variant = pick_variant(_HORDEATH_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s"}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/SWANGAT.X -- the Melee attack action itself, the
# sibling to FARR.X's own Fire Arrow attack action. See module
# docstring's Phase 113 addendum.
_SWANGAT_TEMPLATES: list[str] = [
    "< {circled right/Rleft and }{angrily/Rviolently }assailed/Rattacked [",
    "{undaunted/Rshowing_no_fear, }< {moved in/Rcloser and }$S [",
    "< {whirled around/Rabout and }{daringly/Raudaciously }$S [",
    "< {summoned all > will/Rstrength and bravely/Rdesperately }$S > "
    "{fearsome/Rvaunted }enemy/Rnemesis",
    "< {feinted/Rfaked in_one_direction/Rone_way, then crossed/Rswitched "
    "over and }{treacherously/Rviciously }$S [",
    "< {acrobatically/Rflamboyantly flipped/Rvaulted over [ and }"
    "{deftly/Rcontemptuously }$S [",
    "< {feigned/Rpretended_to retreat/Rpanic, then pivoted/Rwhirled and }"
    "{treacherously/Rarrogantly }$S [",
    "{with amazing/Rsurprising speed/Rquickness, }< "
    "{immediately/Renergetically }$S [",
    "{seeking/Rhoping to exploit/Rtake_advantage_of ^A gap/Rweak_point "
    "in ['s defenses/Rprotection, }< {skillfully/Rdeftly }$S [",
    "{< maneuvered/Rshifted_over for/Rto a better/Rgood "
    "attacking/Rdefensive position/Rvantage.then }< $S [{ with all > "
    "might/Rstrength}",
    "{< forced/Rturned back/Raway [ with > aggressive/Rspirited "
    "assault/Rtactics.}< then $S [{ with terrific/Rmaximum force/Rstrength}",
]


def render_melee_attack(
    character_name: str, opponent_name: str, attack_method: str, rng: random.Random
) -> str:
    """Renders SWANGAT.X's sentence for the Melee attack action itself
    -- no trailing punctuation, meant to be immediately followed by
    ``render_attack_missed()``/``render_attack_hit()``/
    ``render_attack_devastating_hit()`` to form one complete sentence,
    the same shape ``render_fire_arrow_attack()`` established. Unlike
    Fire Arrow, Melee has no fixed weapon/verb, so ``attack_method`` is
    an explicit caller-supplied parameter (``PROSE.TXT``'s own ``$S``
    marker, e.g. ``"Slashed"``, ``"Thrust"``) rather than hardcoded.
    """

    variant = pick_variant(_SWANGAT_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": opponent_name,
        ">": f"{character_name}'s",
        "$S": attack_method,
    }
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/CCAST.X -- the personal-combat Cast action's own
# flavor variant when no wand item is involved (`SAY.PAS:604 _LCast: IF
# _treas = notreasure THEN FD2('ccast',S_PCom,2)`). Phase 588. `~` is
# `PROSE.TXT`'s own confirmed spell-name marker (`models/power.py`'s
# own precedent).
_CCAST_TEMPLATES: list[str] = [
    "weaving/RChanting > silver/Rartful words of magic into ^A "
    "mighty/Rgreat ~ spell, < waved/Rgestured_with > hands/Rarms",
    "< incanted/Rchanted > mysterious/Rstrange words of magic and cast ^A ~ spell",
    "gesturing_with/Rwaving > hands/Rarms, < orchestrated/Rjuxtaposed "
    "supernatural/Rotherworldly forces of magic, casting ^A ~ spell",
    "raising/Rlifting > hands high in the air/Swaves, < cast ^A ~ spell",
    "chanting/RUttering > words/Rsyllables of magic with "
    "breathless/Rtrained precision, < let go/Rfly ^A ~ spell",
    "incanting/RCasting ^A ~ spell, < directed/Rchannelled "
    "glowing/Rscintillating, interlacing/Rwrithing strands of magic",
]


def render_cast_no_treasure(character_name: str, spell_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders CCAST.X's sentence for a personal-combat Cast action that
    isn't wand-triggered (Phase 588). No trailing punctuation -- ``$S``/
    weapon-style fixed-verb sentences elsewhere in this cluster all
    lack one too, meant to be followed by the spell's own outcome.
    ``is_sea`` (Phase 74) resolves the "/S" marker one variant carries.
    """

    variant = pick_variant(_CCAST_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s", "~": spell_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/FLAMEREL.X -- the Flaming Scimitar's own 5%
# instant-death fireball proc (`models/treasure.py TREASURE_DESCRIPTION
# [Treasure.WEAPON_3]`'s own confirmed mechanic). `SAY.PAS:428 _TrImpl:
# FD2('flamerel',S_PCom,5)`. Phase 588.
_FLAMEREL_TEMPLATES: list[str] = [
    "the Flaming Scimitar released/Rburped ^A fireball which imploded "
    "inside [{, bursting ] body into shreds}.",
    "the magic of the Flaming Scimitar was triggered/Ractivated by the "
    "impact/Rblow and ^A {mighty }fireball imploded inside {the stomach "
    "of }[, blowing [ to bits.",
    "the Flaming Scimitar ignited/Rcombusted ^A imploding fireball in "
    "the innards/Rbelly of [, splattering/Rshowering ] "
    "guts/Rintestines all over in ^A sordid/Rhorrible puke-fest/Rscene.",
]


def render_flaming_scimitar_proc(defender_name: str, rng: random.Random) -> str:
    """Renders FLAMEREL.X's sentence for the Flaming Scimitar's own
    instant-death fireball proc (Phase 588).
    """

    variant = pick_variant(_FLAMEREL_TEMPLATES, rng)
    values = {"[": defender_name, "]": f"{defender_name}'s"}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/SHADTR.X -- the Shadow Sword's own life-drain-heal
# proc (`models/treasure.py TREASURE_DESCRIPTION[Treasure.WEAPON_2]`'s
# own confirmed mechanic). `SAY.PAS:427 _TrShad: FD2('shadtr',S_PCom,
# 4)`. Phase 588. `#` is `PROSE.TXT`'s own confirmed contextual-number
# marker -- the wielder's own new hit-point total after the drain.
_SHADTR_TEMPLATES: list[str] = [
    "the Shadow Sword transferred/Rconducted the {lost }life "
    "energy/Ressence to <2 and > hit points rose/Rjumped {back up }to #.",
    "the Shadow Sword sucked_in/Rdrained_away the life energy/Ressence "
    "lost by [ and > hit points rose/Rjumped {back up }to #.",
    "the Shadow Sword {gleefully/Rgreedily }inhaled/Rsucked_in ['s life "
    "energy/Ressence and imbued/Rinfused <2 with enough/Rsufficient "
    "energy/Rwarmth to raise > hit points to #.",
]


def render_shadow_sword_drain(wielder_name: str, opponent_name: str, new_hit_points: int, rng: random.Random) -> str:
    """Renders SHADTR.X's sentence for the Shadow Sword's own
    life-drain-heal proc (Phase 588). ``<2`` is the wielder (this
    catalog never uses a bare ``<``); ``[``/``]`` the opponent whose
    life energy was drained.
    """

    variant = pick_variant(_SHADTR_TEMPLATES, rng)
    values = {
        "<2": wielder_name,
        ">": f"{wielder_name}'s",
        "[": opponent_name,
        "]": f"{opponent_name}'s",
        "#": str(new_hit_points),
    }
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/RECSTUN.X -- recovering from a stunned state (the
# Psychic Flail's own `models/treasure.py TREASURE_DESCRIPTION[Treasure.
# WEAPON_4]`-confirmed mechanic, and the Psychic Blast spell's own
# stun effect). `SAY.PAS:625 _LRecov: FD2('recstun',S_PCom,1)`. Phase
# 588.
_RECSTUN_TEMPLATES: list[str] = [
    "< shook/Rcleared > head and recovered from > stunned state/Rcondition.",
    "<'s head {finally }cleared and < {once again }prepared/Rreadied for combat/Rbattle.",
    "{now }the {effects of the }stun {finally }wore off and < prepared to {renew > }attack.",
]


def render_stun_recovery(character_name: str, rng: random.Random) -> str:
    """Renders RECSTUN.X's sentence for recovering from a stunned state
    (Phase 588).
    """

    variant = pick_variant(_RECSTUN_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s"}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/STUN.X -- being in a stunned state, the sibling of
# RECSTUN.X above. `SAY.PAS:626 _LStun: FD2('stun',S_PCom,4)`. Phase 588.
_STUN_TEMPLATES: list[str] = [
    "< stood/Sstayed stunned, unable to regain > senses/Rbalance.",
    "stunned, < could only shake > head in bewilderment/Rperplexity.",
    "< was stunned and staggered/Sflopped around at_random/Runsteadily.",
    "< stood dazed{ and bewildered/Rperplexed}, stunned out of > wits/Rmind.",
    "< could do nothing {but stand/Shover and stare }in > stunned state.",
    "in > {pathetic }stunned state, < could not decide/Rdetermine what to "
    "do{ about > predicament}.",
]


def render_stunned(character_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders STUN.X's sentence for being in a stunned state (Phase
    588). ``is_sea`` (Phase 74) resolves the "/S" marker three variants
    carry.
    """

    variant = pick_variant(_STUN_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s"}
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/GLSTEAL.X, GMSTEAL.X, GLSPOILS.X, GMSPOILS.X, TLSTEAL.X,
# TMSTEAL.X, TLSPOILS.X, TMSPOILS.X -- the personal-combat loot cluster
# (Phase 590). `RUMORS.PAS` defines all eight as one small constant block
# (~line 142-145): `T_Conf=3200; T_LSteal=3201; T_MSteal=3202;
# T_LSpoils=3203; T_MSpoils=3204; T_ISpoils=3207; G_Conf=3210;
# G_LSteal=3211; G_MSteal=3212; G_LSpoils=3213; G_MSpoils=3214;
# G_Inher=3215; _MGain=3216; G_ISpoils=3217`, and `SAY.PAS` dispatches
# each through `FD()` (SAY.PAS:558-561, 576-579) exactly like every
# other already-transcribed catalog. The `Steal`/`Spoils` split lines up
# with two real, currently-unnarrated gaps this project's own code
# already has data for: `describe_steal()`'s own docstring (above)
# explicitly says "a clean gold or item theft was never given prose in
# any available source" for `steal_outcome in ("success", "evaded",
# "executed", "unresolved")` -- the `*Steal` half is that prose, now
# found. Separately, `turn/challenge_execution.py`/`turn/pursue_
# execution.py`'s own `looted_item_ids` field (Phase 313, set whenever
# `loser_killed` is True) has never been narrated anywhere in this
# module -- the `*Spoils` half (`GMSPOILS.X`'s own real overflow text,
# "took the list from the corpse of [", confirms Spoils narrates a
# *dead* opponent's belongings) is that prose too.
#
# The `G_`/`T_` prefix pair reuses `render()`'s own Phase 118 `^L`
# list-insertion mechanism exactly as its own docstring already
# describes (`"^L\\"` = a Magic Item list, this module's confirmed
# example) -- `G_*` templates contain `^L\` and narrate a *list* of
# looted items via `lists={"\\": [...]}`; `T_*` templates never contain
# `\` or `^L` at all and instead spell out the plain word "treasure" --
# read here as the `T_*` half firing when there's exactly one named
# `Treasure`-type item involved (no list needed) and `G_*` firing for
# an arbitrary-length list of ordinary items, matching this project's
# own `Treasure` vs. plain `Item` model distinction, though no direct
# Pascal citation confirms that specific selection rule (see below).
#
# **What is NOT resolved, honestly documented rather than guessed**:
# despite these being real, non-compiled-unit Pascal constants (unlike
# an earlier phase's assumption that this kind of dispatch always hides
# in `DEFINES.TPU`), no call site anywhere in the available `.PAS`
# corpus (`CTBOTH.PAS`, `REPORTS.PAS`, `CTME.PAS`, `SAY.PAS`,
# `RUMORS.PAS`, `YAK.PAS`, `AKT.PAS`, `COMPANY.PAS`, `DEF2.PAS`,
# `TRANS.PAS`, `LNAMES.PAS`, `PRNAMES.PAS`, `SAGACHAR.PAS`) ever writes
# any of these eight constant names outside their own two declaration/
# dispatch blocks -- `CTBOTH.PAS:120`'s own `CSteal` (a *different*,
# `story`-vector event-code enum member, not one of these eight) is
# likewise declared but never referenced by name, meaning the
# controlling `CASE` that actually selects between `L`/`M` (and decides
# `G_`/`T_` beyond the list/no-list heuristic above) assigns these
# constants to a variable somewhere rather than writing their names
# literally, which this project's available source can't trace further.
# Following the same "sourced but unwired" precedent Phase 587 already
# set for `LUCKINT_TEMPLATE`/`LUCKINT2_TEMPLATE`: all eight templates
# below are real, byte-faithful, and render-tested, but none is wired
# into `describe_steal()` or any other composer, and the exact `L`
# (mnemonic unconfirmed) vs. `M` (mnemonic unconfirmed) selection rule
# is left an open, flagged gap rather than guessed.
_GLSTEAL_TEMPLATES: list[str] = [
    "< {expertly }pickpocketed/Rrobbed_him_of ] ^L\\.",
    "< {skillfully }stole the ^L\\ belonging_to/Rowned_by [.",
    "< {greedily }pilfered ] ^L\\.",
    "[1 lost ] ^L\\ to > stealthy/Rdexterous fingers.",
]


def render_group_theft_from_survivor(
    thief_name: str, victim_name: str, looted_items: Sequence[str], rng: random.Random
) -> str:
    """Renders GLSTEAL.X's sentence for a successful, uncaught Steal
    against a still-living victim, narrating an arbitrary-length list of
    ordinary looted items via ``^L\\`` (Phase 590). ``looted_items`` are
    already-formatted display strings (e.g. ``"a sword"``), matching
    ``^L``'s own Phase 118 calling convention.
    """

    variant = pick_variant(_GLSTEAL_TEMPLATES, rng)
    values = {
        "<": thief_name,
        ">": f"{thief_name}'s",
        "[": victim_name,
        "[1": victim_name,
        "]": f"{victim_name}'s",
    }
    return render(variant, values, rng=rng, lists={"\\": list(looted_items)})


_GMSTEAL_TEMPLATES: list[str] = [
    "with hands/Rfingers as soft {and quiet/Rsilent }as ^A "
    "zephyr/Rfeather, < carefully/Rsoundlessly pilfered/Rfingered the "
    "^L\\.",
    "breathless/RHeart_racing with nervousness/Rexcitement, < reached "
    "in and stole/Rsecured the ^L\\.",
    "like walking on ^A razor's_edge/Rtightrope, < {carefully/Rslowly "
    "}curled/Rslipped > fingers around the ^L\\.",
    "< grabbed/Rgrasped the ^L\\, > {> narrow }eyes glittering/Rshining "
    "with {uncontrolled/Rnaked }avarice/Rgreed.",
]


def render_group_theft_tense(thief_name: str, looted_items: Sequence[str], rng: random.Random) -> str:
    """Renders GMSTEAL.X's sentence for a successful, uncaught Steal --
    the tenser sibling of ``render_group_theft_from_survivor()``, with
    no victim reference of its own (Phase 590).
    """

    variant = pick_variant(_GMSTEAL_TEMPLATES, rng)
    values = {"<": thief_name, ">": f"{thief_name}'s"}
    return render(variant, values, rng=rng, lists={"\\": list(looted_items)})


_GLSPOILS_TEMPLATES: list[str] = [
    "< grabbed/Rtook the ^L\\{ from ] hoard/Rtreasure}.",
    "< discovered/Rfound the ^L\\.",
    "< rummaged/Rsearched through ['s belongings/Rpossessions and "
    "took/Rfound the ^L\\.",
]


def render_group_spoils_from_survivor(
    looter_name: str, victim_name: str, looted_items: Sequence[str], rng: random.Random
) -> str:
    """Renders GLSPOILS.X's sentence for looting a list of ordinary
    items from a victim's own hoard (Phase 590).
    """

    variant = pick_variant(_GLSPOILS_TEMPLATES, rng)
    values = {"<": looter_name, "[": victim_name, "]": f"{victim_name}'s"}
    return render(variant, values, rng=rng, lists={"\\": list(looted_items)})


# GMSPOILS.X's own physical file declares a `1 1` header (one choice)
# but the real payload has two more complete alternatives past it --
# AKPROSE's own SS5 anomaly section (confirmed independently, not
# guessed by this project) states plainly: "GMSPOILS.X dichiara `1 1`,
# ma contiene altre due alternative complete. La scelta casuale vede
# soltanto la prima: le altre due non sono mai selezionate." -- i.e. a
# real, confirmed historical dead-code anomaly in the original engine
# itself (AKGEN's own header-bound `pick_variant` equivalent could never
# reach choices 2/3), the same category of finding as Phase 580's
# `TREASURE_NAME` gap and Phase 584's BLUCK/CLUCK mislabeling. All three
# real choices are kept here (matching that precedent of preserving
# every real byte found rather than truncating to the declared header),
# with this comment as the honest record of why `pick_variant()` below
# can reach lines the original game engine itself never could.
_GMSPOILS_TEMPLATES: list[str] = [
    "< {walked/Sswam over to ^A pile/Rmound of treasure and "
    "}bagged/Rsecured the ^L\\.",
    "< took/Rstripped the ^L\\ from the corpse/Rremains of [.",
    "the ^L\\ lay nearby, and < picked_up/Rretrieved the treasure.",
]


def render_group_spoils_from_corpse(
    looter_name: str, victim_name: str, looted_items: Sequence[str], rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders GMSPOILS.X's sentence for looting a list of ordinary
    items from a dead opponent's remains (Phase 590) -- the ``loser_
    killed``/``looted_item_ids`` gap this cluster's own module comment
    describes. ``is_sea`` (Phase 74) resolves the "/S" marker the first
    variant carries.
    """

    variant = pick_variant(_GMSPOILS_TEMPLATES, rng)
    values = {"<": looter_name, "[": victim_name}
    return render(variant, values, rng=rng, is_sea=is_sea, lists={"\\": list(looted_items)})


_TLSTEAL_TEMPLATES: list[str] = [
    "< cautiously/Rcarefully laid_hands_on/Rreached for the treasure.",
    "< slid/Rslipped > hands cautiously/Rfondly over the treasure.",
    "< succeeded in laying > {greedy }hands/Rfingers on the treasure.",
    "the treasure seemed {almost }to call out to <2.< "
    "carefully/Rcautiously reached out for it.",
]


def render_treasure_theft_from_survivor(thief_name: str, rng: random.Random) -> str:
    """Renders TLSTEAL.X's sentence for a successful, uncaught Steal of
    a single named ``Treasure`` -- no victim reference of its own, and
    ``<2`` (the same alternate-attacker-reference convention Phase 588's
    SHADTR already established) stands in for a repeated ``<`` within
    one variant (Phase 590).
    """

    variant = pick_variant(_TLSTEAL_TEMPLATES, rng)
    values = {"<": thief_name, ">": f"{thief_name}'s", "<2": thief_name}
    return render(variant, values, rng=rng)


_TMSTEAL_TEMPLATES: list[str] = [
    "< caressed/Rlifted the treasure fondly/Rlovingly.",
    "< {then }beheld the treasure, which lay there just for the taking.",
    "< succeeded in laying > {greedy }hands/Rfingers on the {valuable "
    "}treasure.",
    "< could see the glittering/Rgleaming{, shiny/Rglowing} treasure "
    "which seemed to {seductively }beckon/Rcall_out to > "
    "greedy/Rtrembling fingers.",
]


def render_treasure_theft_tense(thief_name: str, rng: random.Random) -> str:
    """Renders TMSTEAL.X's sentence for a successful, uncaught Steal of
    a single named ``Treasure`` -- the tenser sibling of ``render_
    treasure_theft_from_survivor()`` (Phase 590).
    """

    variant = pick_variant(_TMSTEAL_TEMPLATES, rng)
    values = {"<": thief_name, ">": f"{thief_name}'s"}
    return render(variant, values, rng=rng)


_TLSPOILS_TEMPLATES: list[str] = [
    "< stooped/Rkneeled to recover/Rcollect the {personal }belongings "
    "of [.",
    "< took the bag/Rpack [1 had been_carrying/Rborne.",
    "< retrieved/Rtook the treasure [1 was carrying/Rbearing.",
    "< stripped/Rrelieved [ of {all of }] treasure.",
]


def render_treasure_spoils_from_survivor(looter_name: str, victim_name: str, rng: random.Random) -> str:
    """Renders TLSPOILS.X's sentence for looting a single named
    ``Treasure`` from a victim who's still alive (Phase 590).
    """

    variant = pick_variant(_TLSPOILS_TEMPLATES, rng)
    values = {"<": looter_name, "[": victim_name, "[1": victim_name, "]": f"{victim_name}'s"}
    return render(variant, values, rng=rng)


_TMSPOILS_TEMPLATES: list[str] = [
    "< looked {down }with satisfaction/Rpride at the remains/Rcorpse "
    "of [.",
    "< shifted/Rturned > attention to the treasure/Rhoard of [.",
    "< sacked/Rcleared_out the treasure {chest/Rroom }of [.",
    "< took/Rappropriated the treasure {chest/Rtrove }that once "
    "belonged to [.",
]


def render_treasure_spoils_from_corpse(looter_name: str, victim_name: str, rng: random.Random) -> str:
    """Renders TMSPOILS.X's sentence for looting a single named
    ``Treasure`` from a dead opponent's remains (Phase 590) -- the
    ``loser_killed``/``looted_item_ids`` gap this cluster's own module
    comment describes.
    """

    variant = pick_variant(_TMSPOILS_TEMPLATES, rng)
    values = {"<": looter_name, ">": f"{looter_name}'s", "[": victim_name}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/LSPOILG.X -- the third leg of the defeated-leader-loot
# stool Phase 590 (item lists via `G_*`) and Phase 590's own `T_*`
# (a single named `Treasure`) cover the other two of: a raw gold amount.
# `SAY.PAS:564 _LSpoilG: FD('lspoilg',S_PCom,5)` sits right in the same
# dispatch block as Phase 590's own `G_*`/`T_*` cluster (`T_LSpoils`
# .. `_LSpoilG` .. `G_LSteal`), reinforcing that this is the same
# narrative sequence's gold-specific sibling (Phase 596). Like `BATLDR.X`
# (Phase 593), this is a genuine model gap rather than a missing call
# site: this project's own ``loot_defeated_leader()`` (``turn/
# encounter.py``) only transfers ``ItemInstance``s -- no leader ever
# holds personal gold in this project's model (gold lives at the
# Kingdom-treasury level, `` _LTreas: Say('< was left with # gold in the
# treasury.',...) ``, a different real template entirely), so there is
# no `looted_gold` value to drive this from. Sourced and render-tested,
# not wired into any composer.
_LSPOILG_TEMPLATES: list[str] = [
    "< took/Rlooted # gold from the treasure {trove }of [.",
    "< found/Rlocated ^A treasure of # gold{ and bagged_it/Rsnarfed_it_up}.",
    "< found # gold in the treasure/Rhoard of [.",
]


def render_gold_spoils(looter_name: str, victim_name: str, gold_amount: int, rng: random.Random) -> str:
    """Renders LSPOILG.X's sentence for looting a raw gold amount from a
    defeated leader's treasure (Phase 596). The second variant has no
    victim reference of its own.
    """

    variant = pick_variant(_LSPOILG_TEMPLATES, rng)
    values = {"<": looter_name, "[": victim_name, "#": str(gold_amount)}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/AWANDFR.X, AWANDTO.X, LWANDFR.X, LWANDTO.X -- unemployed
# mercenary armies and Heroes randomly relocating between provinces on
# their own initiative (Phase 591). `SAY.PAS:855-856 _AWandFr: FD('awandfr',
# S_Red,7); _AWandTo: FD('awandto',S_Red,8);` (armies, `=` marker) and
# `SAY.PAS:719/721 _LWandFr: FD('lwandfr',S_Red,3); _LWandTo: FD('lwandto',
# S_Red,4);` (individual Heroes, `<` marker) -- both pairs share the same
# "FR"/"TO" split and the same two-province grammar.
#
# `⟦CTRL-S:province-2⟧` resolves to `^S`, the already-established project
# convention for the real `CTRL-S` binary field (a second province name)
# -- not invented here, already in production use by `render_defensive_
# march()` (Phase 120), `render_illegal_move_non_adjacent()` and its
# siblings (Phase 127), and others. **Direct reading of all 13 real
# choices across these four files (not assumed from another file's own
# `@`/`^S` convention, which points the other way for e.g. `render_
# defensive_march()`) confirms one consistent internal mapping for this
# specific cluster**: `@` is always the province the unit is *leaving*,
# `^S` always the province it's *heading to/just arrived in* -- true in
# every choice of both AWANDFR (`"@ and moved on... to ^S"`) and AWANDTO
# (`"arrived in ^S, having travelled from @"`), so the FR/TO file split
# reflects which report section calls each one (the origin province's own
# report vs. the destination's), not which token means what within the
# sentence itself.
_AWANDFR_TEMPLATES: list[str] = [
    "= grew tired_of/Rbored_with the {wines and }whores/Rcourtesans of "
    "@ and moved_on/Ssailed off to ^S where they hoped the "
    "pickings/Rentertainment would be more to their liking/Rtastes.",
    "= lost hope of finding employment/Radventure in @, {and }so they "
    "mustered their strength and moved_on/Ssailed_away to ^S.",
    "the captain of = felt ^A wanderlust/Rthirst_for_adventure "
    "stirring/Rawakening in his breast/Rheart, and speaking "
    "highly/Reloquently of{ the lands and princes of} ^S, "
    "persuaded/Rconvinced his men to march/Ssail with him to ^S.",
]


def render_mercenary_army_wanders_away(
    army_name: str, origin_province_name: str, destination_province_name: str, rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders AWANDFR.X's sentence for an unemployed mercenary army
    leaving a province on its own initiative (Phase 591). ``is_sea``
    (Phase 74) resolves each variant's own "/S" marker.
    """

    variant = pick_variant(_AWANDFR_TEMPLATES, rng)
    values = {"=": army_name, "@": origin_province_name, "^S": destination_province_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


_AWANDTO_TEMPLATES: list[str] = [
    "= has {just recently }arrived in ^S, having travelled/Rcome from "
    "@{ in search of employment}.",
    "= has wandered/Ssailed into ^S from @.",
    "newly come/Rarrived from @ is =, which army/Snavy is seeking "
    "employment/Ra_liege in ^S.",
]


def render_mercenary_army_wanders_in(
    army_name: str, origin_province_name: str, destination_province_name: str, rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders AWANDTO.X's sentence for an unemployed mercenary army
    arriving in a province on its own initiative (Phase 591). ``is_sea``
    (Phase 74) resolves each variant's own "/S" marker.
    """

    variant = pick_variant(_AWANDTO_TEMPLATES, rng)
    values = {"=": army_name, "@": origin_province_name, "^S": destination_province_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


_LWANDFR_TEMPLATES: list[str] = [
    "< grew bored_with/Rtired_of {the scenery in }@ and departed/Rleft "
    "for ^S.",
    "< awoke/Rarose one morning/Rday with ^A desire/Rwhim to see ^S, "
    "and so left {from }@ to travel/Rjourney to that province.",
    "< heard that ^A old buddy/Rfriend was trapping_furs/Spearl-diving "
    "in ^S and left @ to see > old acquaintance/Rfriend.",
    "< got/Rfell into trouble with the_law/Ra_sheriff in @ and escaped "
    "{imprisonment/Ra_posse }by riding/Ssailing away/Roff to ^S.",
    "< heard stories/Rtales of excellent/Rfine hunting/Sfishing in ^S "
    "and left @ to have_some_fun/Rtake_a_vacation there.",
    "< left @ to attend/Rpreside_over ^A reunion of > old "
    "regiment/Rbattalion in ^S.",
]


def render_character_wanders_away(
    character_name: str,
    origin_province_name: str,
    destination_province_name: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders LWANDFR.X's sentence for an unemployed Hero leaving a
    province on their own initiative -- the individual-character
    sibling of ``render_mercenary_army_wanders_away()`` (Phase 591).
    ``is_sea`` (Phase 74) resolves each variant's own "/S" marker.
    """

    variant = pick_variant(_LWANDFR_TEMPLATES, rng)
    values = {
        "<": character_name,
        ">": f"{character_name}'s",
        "@": origin_province_name,
        "^S": destination_province_name,
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


_LWANDTO_TEMPLATES: list[str] = [
    "< {has }just recently wandered into ^S from @.",
    "< has arrived in ^S from @{, attracted/Rdrawn by the fine/Rgreat "
    "(or infamous?/Rterrible?) reputation of its king}.",
    "< hiked/Ssailed into ^S.< had grown bored/Rtired with @ and was "
    "attracted/Rdrawn there by tales/Rrumors of its fine/Rwonderful "
    "scotch/Rwines{ and even more_wonderful/Rfiner "
    "courtesans/Rchampagnes}.",
    "< rode/Scruised into ^S in search of {worthy }adventure/Remployment"
    "{, having found none/Rnothing_much in @}.",
]


def render_character_wanders_in(
    character_name: str,
    origin_province_name: str,
    destination_province_name: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders LWANDTO.X's sentence for an unemployed Hero arriving in a
    province on their own initiative -- the individual-character sibling
    of ``render_mercenary_army_wanders_in()`` (Phase 591). ``is_sea``
    (Phase 74) resolves each variant's own "/S" marker. The third variant
    is two sentences (the second has no marker of its own, following
    directly after the first with no separator needed).
    """

    variant = pick_variant(_LWANDTO_TEMPLATES, rng)
    values = {
        "<": character_name,
        "@": origin_province_name,
        "^S": destination_province_name,
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/LHAIL.X, LREBUFF.X, LTALKOK.X -- a Talk-to-character
# encounter cluster, all three dispatched at the same `S_PCom` severity
# (Phase 600): `SAY.PAS:762 _LCTalk: FD('lhail',S_PCom,5)` (the opening
# greeting), `SAY.PAS:760 _LRebuff: FD('lrebuff',S_PCom,9)` (the target
# refuses out of a grudge against this Kingdom's own King), and
# `SAY.PAS:757 _LInfo: ELSE FD('ltalkok',S_PCom,8)` (learning a
# wandering Hero's own hiring price -- the natural next step after
# LWANDFR/LWANDTO's own Phase 591 flavor text, though this project's
# ``turn/hire_fire_decode.py`` models only hiring an already-known
# character by name, not a price-discovery negotiation with an
# unemployed one, so this cluster stays sourced but unwired). ``^K``
# (king-title) reuses the same plain-``king_name``-string convention
# already established elsewhere in this module (``render_hire_
# accepted()``'s own ACCHIRE.X, Phase 114).
_LHAIL_TEMPLATES: list[str] = [
    "< {waved/Rheld_forth ^A white flag/Rhandkerchief and "
    "}hailed/Rshouted_out_to [ with {friendly }words of greeting.",
]


def render_hail_greeting(character_name: str, target_name: str, rng: random.Random) -> str:
    """Renders LHAIL.X's sentence for hailing a character to open a Talk
    encounter (Phase 600).
    """

    variant = pick_variant(_LHAIL_TEMPLATES, rng)
    values = {"<": character_name, "[": target_name}
    return render(variant, values, rng=rng)


_LREBUFF_TEMPLATES: list[str] = [
    "< tried_talking/Rspoke to [, but {it seems that }] "
    "family/Rclan holds ^A grudge against ^K{'s clan} and does "
    "not want/Rwish to associate_with/Rserve him.",
    "< spoke to [ with {hopes for }friendship {in > heart}.[1 "
    "rebuffed > overtures/Rgreeting out of personal "
    "dislike/Rdistaste for ^K.",
    "< spoke kindly to [, but was {coldly/Rdisdainfully "
    "}rebuffed because, said [1, \"you and your ilk/Rcronies are "
    "^A gang/Rbunch of SNAKES/RROGUES!\"",
]


def render_talk_rebuffed(character_name: str, target_name: str, king_name: str, rng: random.Random) -> str:
    """Renders LREBUFF.X's sentence for a Talk attempt rebuffed out of a
    grudge against this Kingdom's own King (Phase 600).
    """

    variant = pick_variant(_LREBUFF_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": target_name,
        "[1": target_name,
        "]": f"{target_name}'s",
        ">": f"{character_name}'s",
        "^K": king_name,
    }
    return render(variant, values, rng=rng)


_LTALKOK_TEMPLATES: list[str] = [
    "< talked_to/Rspoke_with [ and learned/Rfound_out that [1 could "
    "be hired/Rbought for # gold.",
    "< spoke/Rconversed with [ for_some_time/Rat_length.< "
    "learned/Rdiscovered that [1 was available {for hire }at ^A "
    "price/Rcost of # gold.",
    "< approached [ and asked/Rinquired if [1 was available.[1 "
    "said/Rdeclared [1 would pledge/Rrent ] allegiance/Rservices "
    "for # gold.",
    "<  found [ {drinking ale/Rbeer }in ^A tavern/Rpub and had ^A "
    "few beers/Rdrinks with [.[1 told/Rinformed <2 that it would "
    "be ] honor/Rpleasure to serve/Rwork_for <2 at the "
    "price/Rcost of # gold.",
]


def render_talk_learned_hire_price(character_name: str, target_name: str, gold_amount: int, rng: random.Random) -> str:
    """Renders LTALKOK.X's sentence for learning a wandering Hero's own
    hiring price via a Talk encounter (Phase 600). The fourth variant's
    own real text has a double space before "found" -- kept verbatim.
    """

    variant = pick_variant(_LTALKOK_TEMPLATES, rng)
    values = {
        "<": character_name,
        "<2": character_name,
        "[": target_name,
        "[1": target_name,
        "]": f"{target_name}'s",
        "#": str(gold_amount),
    }
    return render(variant, values, rng=rng)


def render_valhalla_visitor_rules(visitor_name: str, rng: random.Random) -> list[str]:
    """Renders VALINT.X2's rulebook explanation of the Valhalla
    visiting-Hero mechanic (Phase 606) -- one already-``render()``-ed
    line per real, reachable entry in ``turn/valhalla_execution.py
    VALHALLA_VISITOR_RULES_TEMPLATE`` (see that constant's own comment
    for why the file's real 10th line is deliberately excluded: a
    confirmed header-limit anomaly, never actually printed by the
    original engine). No `/R`/`{...}` in any line, so ``rng`` is unused
    in practice -- kept for signature consistency with every other
    ``render_*()`` composer in this module.
    """

    values = {"[": visitor_name, "[1": visitor_name, "]": f"{visitor_name}'s"}
    return [render(line, values, rng=rng) for line in VALHALLA_VISITOR_RULES_TEMPLATE]


# HostAK/TP/PROSE/THATT.X, THFAIL.X -- the opening/failure bookends of
# the same defeated-leader-treasure-search narrative Phase 590's own
# G_*/T_* Steal/Spoils cluster already covers the success half of
# (Phase 592). `SAY.PAS:834 _LThAtt: FD('thatt',S_PCom,2)` (the search
# opens) and `SAY.PAS:582 _ThFail: FD('thfail',S_PCom,4)` (the search
# comes up empty) sit right alongside that same cluster's own dispatch
# block in `RUMORS.PAS` (`_ThFail=3016` two entries before `T_Conf=3200`'s
# own neighbors start; `_LThAtt=3054`) and share its `S_PCom` context --
# strong circumstantial evidence they're the same narrative sequence's
# open/fail bookends, though (same caveat as Phase 590/591) no call site
# anywhere in the available `.PAS` corpus writes either name outside its
# own declaration/dispatch line, so the exact trigger connecting THATT ->
# {THFAIL | a Steal/Spoils success} can't be traced further. Sourced but
# unwired, matching that same precedent.
_THATT_TEMPLATES: list[str] = [
    "< {stealthily }crept_up_on/Rstole_towards ['s treasure, "
    "hoping/Rwishing to steal ^A great treasure.",
    "< {furtively }stole/Rmoved towards ['s treasure, visions of "
    "wealth/Rgreat_treasure dancing before > eyes.",
    "< searched {soundlessly }for ] treasure.> greedy/Rnervous "
    "fingers twitched in anticipation when < saw the chest/Rvault.",
    "the eyes of < brightened {greedily }when they alighted_on/Rsaw "
    "the treasure trove/Rchest of [.",
    "< {quietly }searched for the treasure of [.Finally < "
    "espied/Rfound ^A hidden/Rconcealed bag/Rchest, and ^A {black "
    "}tide of greed/Ravarice welled/Rgushed up out of > "
    "soul/Rheart{ and filled > dry throat}.",
    "< crept/Rglided {stealthily }into {what I thought was }the "
    "treasure room of [, hands tingling/Rtwitching with "
    "anticipation/Rexcitement.",
]


def render_thief_searches_treasure(searcher_name: str, victim_name: str, rng: random.Random) -> str:
    """Renders THATT.X's sentence for a character beginning to search a
    defeated leader's belongings for treasure (Phase 592) -- precedes
    either ``render_thief_search_failed()`` below or one of Phase 590's
    ``render_*_spoils_from_corpse()``/``render_*_theft_*()`` renderers.
    """

    variant = pick_variant(_THATT_TEMPLATES, rng)
    values = {
        "<": searcher_name,
        ">": f"{searcher_name}'s",
        "[": victim_name,
        "]": f"{victim_name}'s",
    }
    return render(variant, values, rng=rng)


_THFAIL_TEMPLATES: list[str] = [
    "but after searching {fruitlessly }for {half }an hour, < failed "
    "to find any treasure{ of significant/Rhigh value}.",
    "< {patiently/Rcarefully }searched the {entire }area, but {< "
    "}could not find any {valuable }treasure and departed/Rleft in "
    "{total }frustration.",
    "< had {high }hopes of hauling/Rcarting away ^A "
    "{great/Rvaluable }hoard/Rtreasure.But {any amount of "
    "}searching could not reveal/Runcover treasure of any "
    "{measureable/Rappreciable }value/Rworth.",
]


def render_thief_search_failed(searcher_name: str, rng: random.Random) -> str:
    """Renders THFAIL.X's sentence for a treasure search coming up
    empty (Phase 592) -- the failure sibling of ``render_thief_
    searches_treasure()``. No victim reference of its own. The first
    variant's own leading lowercase "but" is verbatim from the real
    source, meant to continue directly after THATT.X's own sentence
    rather than start a fresh one.
    """

    variant = pick_variant(_THFAIL_TEMPLATES, rng)
    values = {"<": searcher_name}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/TGETAWAY.X -- a third Steal-failure flavor, distinct
# from THATT.X/THFAIL.X above (Phase 592, "found nothing at all"): the
# thief finds the treasure but can't actually get away with it -- locked
# in a vault, an unpickable lock, or (choice 3) turns out to be a fake
# once already stolen (Phase 602). `SAY.PAS:658 _LGetAw: FD('tgetaway',
# S_PCom,6)` sits immediately after the already-wired Ice-steal-block
# cluster (`_LWMelt`/`_LSFroz`/``render_ice_steal_blocked``) and right
# before `_LSeen` (``SNEAKUP.X``, caught mid-theft) -- squarely inside
# the same Steal-tactic outcome sequence `describe_steal()`'s own
# docstring already covers, but naming a distinct outcome ("inaccessible
# treasure") that vocabulary doesn't have a value for. Same "sourced but
# unwired" stance as Phase 590's own `*Steal`/`*Spoils` cluster: adding
# this would need a new `steal_outcome` category in `turn/challenge_
# execution.py _resolve_steal_tactic()` with a probabilistic trigger
# this project has no source for, out of scope for a transcription
# phase.
_TGETAWAY_TEMPLATES: list[str] = [
    "but the treasure/Rwealth of [ was encased/Rcontained in "
    "thick steel/Rglass, and < could not find ^A way into the "
    "treasure.",
    "< slid/Rstole up to the treasure {chest }of [, but could "
    "not pick/Ropen the lock and had to leave without any "
    "treasure.",
    "< found {what seemed to be }the treasure of [, but after < "
    "had stolen/Rtaken it < examined/Rlooked_at it {more "
    "carefully }and discovered {to > chagrin/Rdismay }that it "
    "was just ^A cheap imitation/Rfake.",
]


def render_steal_treasure_inaccessible(character_name: str, victim_name: str, rng: random.Random) -> str:
    """Renders TGETAWAY.X's sentence for a Steal attempt that finds the
    treasure but can't actually make off with it (Phase 602). The first
    variant's own leading lowercase "but" is verbatim from the real
    source, the same convention ``render_thief_search_failed()``'s own
    first variant already established.
    """

    variant = pick_variant(_TGETAWAY_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s", "[": victim_name}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/BATLDR.X -- a King/Hero personally commanding a battle
# column into the fray (Phase 593). `SAY.PAS:1038 _attl: IF lp <=
# cdrdex[fn] THEN FD('batldr',S_Batt,2)` -- fires when the column's
# front-line position (`lp`) falls within the commander-index bound
# (`cdrdex[fn]`), i.e. when a leader is actually standing at the head of
# that column. This project's own ``turn/battle_resolution.py
# BattleColumnResult`` has no per-column "commanding leader" field to
# drive that condition from, so (same pattern as Phase 590/591/592)
# this is transcribed and render-tested but not wired into any battle
# composer -- a model gap, not a missing call site this time, but the
# same honest "sourced, not yet reachable from live game state" stance.
# ``<3`` is documented (module docstring's own Phase 131-era note above)
# as just another person/tense variant of the character reference,
# substituted with the same literal commander name as ``<``/``<2``.
_BATLDR_TEMPLATES: list[str] = [
    "<3 led > armies/Snavies {boldly/Rcourageously }into the "
    "battle/Rfray.",
    "<3 stood ready/Rdeterminedly at the head of > thousands/Sships.",
    "<3 commanded/Rled a_host/San_armada of loyal_soldiers/Sfighting_"
    "sail{ into the battle}.",
    "standing at_the_ready/Rtall with > warriors/Sships was <3.",
    "<3 marched/Ssailed with > loyal troops/Ssquadrons, "
    "eyes/Rjaws set in grim/Rterrible determination/Rresolution.",
]


def render_battle_leader_intro(commander_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders BATLDR.X's sentence for a King/Hero personally commanding
    a battle column (Phase 593). ``is_sea`` (Phase 74) resolves each
    variant's own "/S" marker -- every one of the five carries one.
    """

    variant = pick_variant(_BATLDR_TEMPLATES, rng)
    values = {"<3": commander_name, ">": f"{commander_name}'s"}
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/MCOME.X, MFIGHT.X -- a Feature's own guardian monster
# joining a battle to help its Druidic-aligned side (Phase 604), then
# how much it helped. `SAY.PAS:1086-1091 _BMonst: BEGIN chief_on:=
# false; FD('mcome',S_Batt,0); FD('mfight',S_Batt,1001+Rint); chief_on:=
# true; END` -- the two fire back to back for the same event. `turn/
# druidic_monster_aid.py find_druidic_monster_assistance()` (Phase 453,
# wired into `turn/battle_orchestrator.py`'s own battle setup) computes
# exactly this real game-state fact -- `{column: strength_bonus}`, one
# entry per monster that rolled successfully and claimed a column -- but
# it's consumed straight into `resolve_battle()`'s own combat math and
# never retained anywhere afterward (no ``BattleReport`` field records
# which column got help, or which ``Feature``/monster it came from), so
# there's no way to narrate this with real names after the fact without
# a `battle_orchestrator.py` change of its own. Sourced and
# render-tested, not wired -- the same model-gap shape as Phase 593's
# own `BATLDR.X`.
_MCOME_TEMPLATES: list[str] = [
    "[, hearing/Rlearning of the peril/Rjust_cause of the Druidic "
    "king/Rmonarch, arrived_at/Rrushed_to the battle{field} to "
    "fight/Rjoin_forces with =.",
    "word/Rnews of the impending/Rperilous battle had spread {far "
    "and wide }throughout/Rwithin @, so_that/Rand even [ "
    "heard/Rgot_wind of it and made_an_appearance/Rarrived_for_the_"
    "show, where [ fought/Rparticipated alongside/Rwith =.",
    "fighting_with/Rhelping = in the_battle/Rthis_contest was [, "
    "who_had_come/Rcoming to the aid/Rdefense of ] friend/Rally, "
    "the Druidic King/Rruler.",
]


def render_monster_reinforcement_arrives(monster_name: str, army_name: str, province_name: str, rng: random.Random) -> str:
    """Renders MCOME.X's sentence for a Feature's own guardian monster
    arriving to join a battle (Phase 604). Only the second variant uses
    ``province_name`` -- the other two don't reference the province at
    all.
    """

    variant = pick_variant(_MCOME_TEMPLATES, rng)
    values = {"[": monster_name, "=": army_name, "@": province_name, "]": f"{monster_name}'s"}
    return render(variant, values, rng=rng)


_MFIGHT_TEMPLATES: list[str] = [
    "[ was of some slight help/Rassistance in the battle/Rcontest.",
    "[ increased/Raugmented the strength of = considerably/Rsignificantly.",
    "It is_safe_to_say/Rappeared that [ greatly/Rpowerfully "
    "magnified/Renhanced the efforts/Rpower of =.",
    "the presence/Raid of [ was almost/Rjust like having another army!",
    "[ more_than_doubled/Ralmost_tripled the strength of =!",
]


def render_monster_reinforcement_helped(monster_name: str, army_name: str, rng: random.Random) -> str:
    """Renders MFIGHT.X's sentence for how much a guardian monster's aid
    helped a battle (Phase 604) -- meant to follow directly after
    ``render_monster_reinforcement_arrives()``, the same real
    back-to-back dispatch ``SAY.PAS``'s own `_BMonst` uses.
    """

    variant = pick_variant(_MFIGHT_TEMPLATES, rng)
    values = {"[": monster_name, "=": army_name}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/BINOCPR.X -- the Binoculars item's own scouting-preview
# sentence, describing a neighboring province seen from a distance
# (Phase 594). `SAY.PAS:739 _LBinoc: FD('binocpr',S_Red,5)`.
#
# Every marker resolves through an already-established project
# convention, not a new one invented for this phase: `*` (direction) is
# `PROSE.TXT`'s own documented symbol (module docstring line 32), simply
# never wired into a live `values` dict before now; `` ` `` (terrain,
# already live at line 8843's `describe_rumor()`); `@` (province name);
# `^A` (article, `render()`'s own Phase 584 mechanism); `^P` (province
# number, the same `str(encode_hex_number(...))` convention `render_
# march()`/`describe_rumor()` already established, Phase 104/247 --
# *not* `models/map.py province_code()`, a different scheme reserved for
# the still-unimplemented ASCII-map work); `^R` (race name, already live
# at line 5983); `[3` (a King/ruler reference, the same convention
# `render_ally_proposed()` already uses). Only `$W` ("ricchezza"/wealth,
# a raw `$`-prefixed CTRL macro) has no resolved game-mechanic precedent
# anywhere in this project -- this module doesn't invent a wealth-tier
# system for it, matching its own docstring's stance ("does not know
# anything about `GameState` or what a report should say"); `wealth_
# descriptor` is a plain caller-supplied string, the same pattern `$S`
# (`attack_method`) and `$o` (`alignment_name`) already established for
# other `$`-family markers.
#
# The fifth variant's own real text is `*ern horizon` -- `*` substitutes
# a bare compass word (`DIRECTION_NAME`'s own "east"/"northeast"/etc.),
# and `-ern` is real, verbatim source text immediately following it, not
# something this phase adds (confirmed correct for all six `Direction`
# values: "eastern", "northeastern", "southeastern", "southwestern",
# "western", "northwestern").
_BINOCPR_TEMPLATES: list[str] = [
    "to the * lies ^A $W ` province/Rarea called/Rnamed @ ^P, "
    "populated by ^R.It is ruled by [3.",
    "looking/Rturning to the *, one can_see/Respies ^A $W ` area, "
    "which is known as @ ^P.It is populated by ^R and [3 rules "
    "there.",
    "* of here is @ ^P, ^A $W ` province/Rarea owned/Rruled by [3, "
    "where ^R dwell.",
    "to the * there lies/Ris ^A ` province known as @ ^P, ^A $W "
    "land/Sarea of ^R where [3 rules/Rreigns.",
    "viewing the *ern horizon, a_man/Rone can see ^A $W ` province "
    "called/Rknown_as @ ^P.It is said that [3 reigns/Ris_the_ruler "
    "there.It is known to be occupied/Rpopulated by ^R.",
    "* of here lies the $W province of @ ^P, ruled by [3.It is "
    "said/Rknown to be ^A ` province inhabited/Roccupied by ^R.",
]


def render_binoculars_preview(
    direction: str,
    wealth_descriptor: str,
    terrain_name: str,
    province_name: str,
    province_number: str,
    race_name: str,
    ruler_name: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders BINOCPR.X's sentence for the Binoculars item's own
    scouting preview of a neighboring province (Phase 594). Every
    parameter is an already-resolved display string or the exact
    already-established substitution this module's other renderers use
    for the same marker -- see the module comment above for each one's
    own precedent citation. ``is_sea`` (Phase 74) resolves the fourth
    variant's own "/S" marker.
    """

    variant = pick_variant(_BINOCPR_TEMPLATES, rng)
    values = {
        "*": direction,
        "$W": wealth_descriptor,
        "`": terrain_name,
        "@": province_name,
        "^P": province_number,
        "^R": race_name,
        "[3": ruler_name,
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# Phase 415: describe_search()'s own default when narrating a
# SearchExecutionResult.melee_swing -- this project has no per-character
# weapon model (turn/encounter.py Combatant carries no weapon field), so
# there's no source to vary $S by. A fixed, project-original default,
# not a guess at a specific sourced verb -- matches SWANGAT.X's own
# first template's literal "assailed/Rattacked" wording (_SWANGAT_
# TEMPLATES[0] above), so it stays consistent with the real source
# text's own vocabulary even though it isn't itself sourced per-call.
_MELEE_ATTACK_METHOD = "Attacked"


# Project-original, not sourced from PROSE.TXT (Phase 155) -- see module
# docstring's own Phase 155 addendum for the user's exact footnote text
# and provenance. Each is a single, complete sentence (unlike FARR.X's
# own attack+continuation split) -- only one wording was supplied per
# case, so there's no variant list to pick from.
_BREATH_WEAPON_HIT_TEMPLATE = "The < breathes, and the impact deals # damage points."
_BREATH_WEAPON_MISSED_TEMPLATE = "The < breathes, but [ miraculously manages to evade it!"


def render_breath_weapon_hit(monster_type_name: str, defender_name: str, damage_points: int, rng: random.Random) -> str:
    """Renders the project-original breath-weapon hit sentence (dragons,
    Chimera -- see ``missile_attack_flavor()``). ``monster_type_name``
    is the specific species' own display name (e.g. "Red Dragon").
    """

    values = {"<": monster_type_name, "[": defender_name, "#": str(damage_points)}
    return render(_BREATH_WEAPON_HIT_TEMPLATE, values, rng=rng)


def render_breath_weapon_missed(monster_type_name: str, defender_name: str, rng: random.Random) -> str:
    """Renders the project-original breath-weapon miss sentence."""

    values = {"<": monster_type_name, "[": defender_name}
    return render(_BREATH_WEAPON_MISSED_TEMPLATE, values, rng=rng)


_BOULDER_THROW_HIT_TEMPLATE = "The < hurls a huge boulder, and the impact deals # damage points."
_BOULDER_THROW_MISSED_TEMPLATE = "The < hurls a huge boulder, but [ dodges it."


def render_boulder_throw_hit(monster_type_name: str, defender_name: str, damage_points: int, rng: random.Random) -> str:
    """Renders the project-original boulder-throw hit sentence (Giant --
    see ``missile_attack_flavor()`` and module docstring's own note on
    why Treant/Titan don't reach this renderer despite the footnote's
    own text naming them too).
    """

    values = {"<": monster_type_name, "[": defender_name, "#": str(damage_points)}
    return render(_BOULDER_THROW_HIT_TEMPLATE, values, rng=rng)


def render_boulder_throw_missed(monster_type_name: str, defender_name: str, rng: random.Random) -> str:
    """Renders the project-original boulder-throw miss sentence."""

    values = {"<": monster_type_name, "[": defender_name}
    return render(_BOULDER_THROW_MISSED_TEMPLATE, values, rng=rng)


_PETRIFYING_GAZE_HIT_TEMPLATE = "The < casts a petrifying gaze, and [ takes # damage points."
_PETRIFYING_GAZE_MISSED_TEMPLATE = "The < casts a gaze, but [ evades it."


def render_petrifying_gaze_hit(monster_type_name: str, defender_name: str, damage_points: int, rng: random.Random) -> str:
    """Renders the project-original petrifying-gaze hit sentence
    (Basilisk, Medusa -- see ``missile_attack_flavor()``).
    """

    values = {"<": monster_type_name, "[": defender_name, "#": str(damage_points)}
    return render(_PETRIFYING_GAZE_HIT_TEMPLATE, values, rng=rng)


def render_petrifying_gaze_missed(monster_type_name: str, defender_name: str, rng: random.Random) -> str:
    """Renders the project-original petrifying-gaze miss sentence."""

    values = {"<": monster_type_name, "[": defender_name}
    return render(_PETRIFYING_GAZE_MISSED_TEMPLATE, values, rng=rng)


_TROLL_REGENERATION_TEMPLATE = "Horror! The < is regenerating its wounds."


def render_troll_regeneration(monster_type_name: str, rng: random.Random) -> str:
    """Renders the project-original Troll-regeneration combat message
    (``turn/encounter.py``'s own Phase 155 addendum for the mechanical
    half, ``Combatant.regenerates_hp``).
    """

    values = {"<": monster_type_name}
    return render(_TROLL_REGENERATION_TEMPLATE, values, rng=rng)


def missile_attack_flavor(weapon: Weapon) -> str | None:
    """Classifies a monster's own ``models/weapon.py
    MONSTER_RANGED_WEAPON`` assignment into one of Phase 155's three
    project-original narration categories -- ``"breath_weapon"``,
    ``"boulder_throw"``, ``"petrifying_gaze"`` -- or ``None`` for every
    other weapon (the caller falls back to the generic
    ``render_fire_arrow_attack()``/``render_attack_hit()``/
    ``render_attack_missed()`` triplet, Phase 111-112). See module
    docstring's own Phase 155 addendum for the Titan/Treant discrepancy
    this classification deliberately does *not* paper over.
    """

    if weapon in (Weapon.FLAME_BREATH, Weapon.SPIT_ACID, Weapon.POIS_BREATH):
        return "breath_weapon"
    if weapon is Weapon.BOULDER:
        return "boulder_throw"
    if weapon is Weapon.GAZE:
        return "petrifying_gaze"
    return None


# HostAK/TP/PROSE/ACCHIRE.X -- a successful Hire. See module
# docstring's Phase 114 addendum.
_ACCHIRE_TEMPLATES: list[str] = [
    "< spoke {urgently/Reloquently }to [ {of the greatness/Rgrandness "
    "of ^K's realm/Rempire }and convinced [ to pledge ] "
    "allegiance/Rservices to ^K.",
]


def render_hire_accepted(character_name: str, hireling_name: str, king_name: str, rng: random.Random) -> str:
    """Renders ACCHIRE.X's sentence for a successful Hire
    (``turn/hire_fire_decode.py``'s already-modeled ``HireRequest``,
    Phase 17). ``king_name`` is ``PROSE.TXT``'s own ``^K`` marker.
    """

    variant = pick_variant(_ACCHIRE_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": hireling_name,
        "]": f"{hireling_name}'s",
        "^K": king_name,
    }
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/REFHIRE.X -- a refused Hire (alignment/enmity
# reasons). See module docstring's Phase 114 addendum.
_REFHIRE_TEMPLATES: list[str] = [
    "[1 refused to join/Rassociate with ^K, citing/Rtelling_of ^A "
    "{long-held }clan/Rfamily enmity/Rfeud with ^K's alignment.",
    "[1 rebuffed/Rrejected <'s offer of employment, "
    "disdaining/Rridiculing ^K's alignment and saying \"That ^K is "
    "the most infamous/Rtyrannical ruler/Rdespot in the land/Rworld!\"",
    "[1 turned down {the offer of }employment, "
    "expressing/Rtelling_of ] disgust/Rdisdain for ^K's alignment and "
    "criticizing/Rberating ^K for \"Holding/R\"Keeping ^A palace court "
    "staffed/Rfilled with buffoons/Rgoons{ and slimy/Robsequious "
    "weasels/Rrodents}!\"",
]


def render_hire_refused(character_name: str, hireling_name: str, king_name: str, rng: random.Random) -> str:
    """Renders REFHIRE.X's sentence for a Hire refused over alignment
    -- distinct from ``render_hire_counter_offer()``'s own price
    -based refusal below. ``king_name`` is ``PROSE.TXT``'s own ``^K``
    marker.
    """

    variant = pick_variant(_REFHIRE_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[1": hireling_name,
        "]": f"{hireling_name}'s",
        "^K": king_name,
    }
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/FIREMAN.X -- a Fire. See module docstring's Phase
# 114 addendum.
_FIREMAN_TEMPLATES: list[str] = [
    "< told/Rinformed [ that [1 was no longer ^A useful "
    "employee/Rasset to ^K, and relieved [ of ] position/Rduties.",
    "< canned/Rfired [, saying_to/Rtelling [ that [1 \"was no longer "
    "worth ] salt\".",
    "< relieved [ of ] responsibilities/Rduties and released [ into "
    "private life.",
    "< fired/Rblackballed [ and told [ to find employment/Rwork elsewhere.",
]


def render_fire_hireling(character_name: str, hireling_name: str, king_name: str, rng: random.Random) -> str:
    """Renders FIREMAN.X's sentence for a Fire
    (``turn/hire_fire_decode.py``'s already-modeled ``FireRequest``,
    Phase 17). ``king_name`` is ``PROSE.TXT``'s own ``^K`` marker (only
    the first variant uses it).
    """

    variant = pick_variant(_FIREMAN_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": hireling_name,
        "[1": hireling_name,
        "]": f"{hireling_name}'s",
        "^K": king_name,
    }
    return render(variant, values, rng=rng)


# HostAK/TP/SAY.PAS _LCounter -- a single, real, hardcoded template (no
# file), a price-based Hire refusal distinct from REFHIRE.X's own
# alignment-based one. See module docstring's Phase 114 addendum.
HIRE_COUNTER_OFFER_TEMPLATE = "[1 informed <2 that [1 would not sell ] services for less than # gold."


def render_hire_counter_offer(
    character_name: str, hireling_name: str, minimum_gold: int, rng: random.Random
) -> str:
    """Renders ``_LCounter``'s sentence for a Hire refused over price."""

    values = {
        "[1": hireling_name,
        "<2": character_name,
        "]": f"{hireling_name}'s",
        "#": str(minimum_gold),
    }
    return render(HIRE_COUNTER_OFFER_TEMPLATE, values, rng=rng)


def describe_hire(
    result: HireExecutionResult,
    *,
    character_name: str,
    hireling_name: str,
    king_name: str,
    rng: random.Random,
) -> str | None:
    """Assembles the one-sentence Hire narrative from an already-computed
    ``HireExecutionResult`` (``turn/plan_dispatch.py _dispatch_hire()``,
    Phase 17) -- the same ``describe_give()``-style composer (Phase 142).

    **Phase 162 unblocks the other two renderers**: ``_dispatch_hire()``
    now computes a real required pay (``turn/hire_pay.py
    required_pay()``) instead of always accepting a co-located,
    affordable offer, giving both ``render_hire_refused`` (``REFHIRE.X``,
    reason ``"alignment gap too wide"``) and ``render_hire_counter_offer``
    (``_LCounter``, reason ``"offer below required pay"``, using
    ``result.minimum_gold``) their first real triggers. The remaining
    failure strings ("hero not found", "cannot hire a King", "hero
    already in service", "not co-located", "insufficient treasury") stay
    administrative, with no sourced narrative template -- same as most
    of ``describe_give()``'s own failure reasons.
    """

    if result.hired:
        return render_hire_accepted(character_name, hireling_name, king_name, rng)
    if result.reason == "alignment gap too wide":
        return render_hire_refused(character_name, hireling_name, king_name, rng)
    if result.reason == "offer below required pay" and result.minimum_gold is not None:
        return render_hire_counter_offer(character_name, hireling_name, result.minimum_gold, rng)
    return None


def describe_fire(
    result: FireExecutionResult,
    *,
    character_name: str,
    hireling_name: str,
    king_name: str,
    rng: random.Random,
) -> str | None:
    """Assembles the one-sentence Fire narrative from an already-computed
    ``FireExecutionResult`` (``turn/plan_dispatch.py _dispatch_fire()``,
    Phase 143 -- see that function's own docstring for why it now
    returns a real result instead of a bare ``FireRequest``).

    ``render_fire_hireling`` (``FIREMAN.X``) on success; both of
    ``FireExecutionResult``'s real failure reasons ("hero not found",
    "not co-located") have no sourced narrative template.
    """

    if result.fired:
        return render_fire_hireling(character_name, hireling_name, king_name, rng)
    return None


# HostAK/TP/PROSE/RECRUIT.X -- one sentence per unit actually recruited
# (Phase 419), covering the freshly-levied case. **Phase 595 update**:
# the hired-mercenary-vs-freshly-levied distinction (``RecruitedUnit.
# hired``) *does* have a real, dedicated sourced template after all --
# ``HIREMERC.X`` below, dispatched by ``SAY.PAS:847 _AHired: FD(
# 'hiremerc',S_AA,4)``, a direct sibling of ``_ARecr: FD('recruit',
# S_AA,3)`` (``RUMORS.PAS``'s own constant block declares them
# adjacently: ``_ARecr=4000; _AHired=4001``) -- so these 4 style
# variants are used only for ``hired=False`` units; style still picked
# uniformly among them since nothing further ties a *specific* one of
# the 4 to any other distinction.
RECRUIT_TEMPLATES: list[str] = [
    "< recruited/Rlevied = from among the people/Rpopulation of @, to serve under [.",
    "< levied/Renlisted = in @ to serve [.",
    "< announced  plea/Rcall for volunteers/Rrecruits in @ and was able to form/Renlist = to fight for [.",
    "< enlisted/Rrecruited enough men in @ to create/Rform = for the army of [.",
]


def _unled_army_commander_name(province: ProvinceState) -> str:
    """Resolves the ``[`` marker for an army whose ``commanded_by`` is
    ``None`` -- shared by ``describe_recruit()`` (Phase 419) and
    ``describe_leave()`` (Phase 420), since both narrate through an
    ``FD`` call at ``S_AA`` severity (``_ARecr``/``_ALeave`` in
    ``SAY.PAS``) and so both resolve `RUMORS.PAS Pronoun()`'s own
    ``chief_on`` branch identically -- see ``describe_recruit()``'s own
    docstring for the full sourcing of why ``S_AA > S_Batt`` makes the
    ``"the provincial garrison commander"`` branch the only real
    outcome here, not ``AC_Say``'s ``"the acting commander"``.
    """

    return (
        "the provincial garrison commander"
        if province.race in HUMANOID_RACES
        else f"the provincial {RACE_NAME[province.race]} chieftain"
    )


def render_recruit_unit(
    recruiter_name: str, province_name: str, army_type_name: str, commander_name: str, rng: random.Random
) -> str:
    """Renders RECRUIT.X's sentence for a single recruited unit -- ``<``
    the recruiter, ``@`` the province, ``=`` the army type's designation
    (Phase 419), ``[`` the leader the unit now serves under (see
    ``describe_recruit()`` for how an unled unit's ``[`` is resolved).
    """

    variant = pick_variant(RECRUIT_TEMPLATES, rng)
    values = {"<": recruiter_name, "@": province_name, "=": army_type_name, "[": commander_name}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/HIREMERC.X -- RECRUIT.X's own hired-mercenary sibling
# (Phase 595, see the module comment above ``RECRUIT_TEMPLATES``). Uses
# ``^L=`` (``⟦CTRL-L:list⟧=``) -- the exact canonical ``^L`` example this
# project's own ``report/prose.py`` module docstring already quotes
# verbatim ("^L=", where "=" means "army"). No ``[`` (served-under
# leader) in any of the 3 variants -- confirmed not just from the text
# itself but from ``SAY.PAS``: unlike ``_ARecr``, ``_AHired`` never sets
# ``chief_on`` before its own ``FD`` call, the same signal ``describe_
# recruit()``'s own Phase 419 docstring already reads for the opposite
# case. One sentence per hired unit, each with a single-item list
# (renders bare, no "and") -- matching ``RECRUIT.X``'s own established
# one-sentence-per-unit call pattern rather than guessing at a
# multi-unit merge this project has no other precedent for building.
HIREMERC_TEMPLATES: list[str] = [
    "< hired ^L=, ^A {redoubtable/Rwell-drilled }mercenary "
    "army/Ssquadron which had made_its_way_to/Rarrived_in @.",
    "< recruited ^A {rough/Rhard_fighting }band/Rforce of mercenary "
    "soldiers/Sships in @ who call_themselves/Rare_known_as ^L=.",
    "< negotiated_with/Rproposed_terms_to ^L= for their "
    "allegiance/Rsupport, and succeeded in contracting_for/Rsecuring "
    "their services/Renlistment.",
]


def render_recruit_hired_mercenary(
    recruiter_name: str, province_name: str, army_type_name: str, rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders HIREMERC.X's sentence for hiring an existing mercenary
    army rather than levying a fresh unit (Phase 595). ``is_sea`` (Phase
    74) resolves each of the first two variants' own "/S" marker.
    """

    variant = pick_variant(HIREMERC_TEMPLATES, rng)
    values = {"<": recruiter_name, "@": province_name}
    return render(variant, values, rng=rng, is_sea=is_sea, lists={"=": [army_type_name]})


def describe_recruit(
    result: RecruitExecutionResult,
    state: GameState,
    *,
    recruiter_name: str,
    province: ProvinceState,
    rng: random.Random,
) -> list[str]:
    """Assembles one RECRUIT.X sentence per ``result.recruited`` unit
    (Phase 419) -- the blocked-request lists (``limit_blocked``,
    ``gold_blocked``, ``incompatible``, ``treat_blocked``,
    ``territory_blocked``) have no sourced narrative template, matching
    this project's "no source, no guess" stance for administrative
    rejections elsewhere (e.g. ``describe_encounter_combat()``'s own
    Phase 417 precedent).

    **The ``[`` (commander) marker, when a unit is unled**
    (``ArmyState.commanded_by is None``): ``RUMORS.PAS Pronoun()``'s own
    ``chief_on`` branch (set around ``_ARecr``'s ``FD`` call in
    ``SAY.PAS``) resolves this deterministically, not by guesswork --
    - the province's race is monstrous (``not in HUMANOID_RACES``) ->
      ``"the provincial <race> chieftain"`` (``RACE_NAME``-driven,
      exactly `Pronoun()`'s own ``Concat('the provincial ',
      rname[...],' chieftain')``);
    - otherwise -> ``"the provincial garrison commander"``, **not**
      ``AC_Say``'s ``"the acting commander"`` -- `Pronoun()`'s own
      ``IF spytype <= S_Batt THEN AC_Say ELSE Say('the provincial
      garrison commander', spytype)`` branches on the report-severity
      argument `FD` was called with, and `_ARecr`'s own call
      (``FD('recruit', S_AA, 3)``) fixes that at ``S_AA`` -- strictly
      greater than ``S_Batt`` in ``CTBOTH.PAS``'s own severity-constant
      order (``S_Prev``..``S_Comm``), so the ``ELSE`` branch is the one
      and only real outcome for this specific call site, not a
      runtime-varying choice this project would have to guess between.
      Shared with ``describe_leave()`` (Phase 420) via
      ``_unled_army_commander_name()``.

    **Deliberately not rendered here**: ``_AAPay`` ("< paid # gold to
    [ for the privilege of recruiting these troops.", the ally-fee
    sentence) -- ``RecruitExecutionResult`` doesn't currently carry
    which unit (if any) paid an ally fee, or how much, only each
    ``RecruitedUnit.gold_paid``'s already-combined total (own cost +
    ally fee). Left for a future phase rather than guessed here.

    **Phase 595**: ``unit.hired`` (``turn/recruit_execution.py``'s own
    "an existing mercenary was hired, not freshly levied" flag) now
    routes to ``render_recruit_hired_mercenary()`` (``HIREMERC.X``)
    instead of ``render_recruit_unit()`` (``RECRUIT.X``) -- see that
    function's own module comment for the ``SAY.PAS``/``RUMORS.PAS``
    sourcing confirming these are real sibling outcomes of the same
    dispatch, not a guessed split. No ``[`` marker in ``HIREMERC.X``, so
    the commander-resolution logic above only runs for unhired units.
    """

    lines: list[str] = []
    province_name = _province_label(state, province.coord)
    is_sea = province.effective_terrain() is Terrain.SEA
    for unit in result.recruited:
        army_type_name = ARMY_TYPE_DESIGNATION[unit.army_type]
        if unit.hired:
            lines.append(render_recruit_hired_mercenary(recruiter_name, province_name, army_type_name, rng, is_sea=is_sea))
            continue
        army = state.armies.get(unit.army_id)
        commander_id = army.commanded_by if army is not None else None
        commander_name = _leader_name(state, commander_id)
        if commander_name is None:
            commander_name = _unled_army_commander_name(province)
        lines.append(render_recruit_unit(recruiter_name, province_name, army_type_name, commander_name, rng))
    return lines


# HostAK/TP/PROSE/LEAVE.X -- one sentence per unit actually left behind
# (Phase 420). The lone ``{encamped/Sanchored }`` optional block (variant
# 3) resolves via terrain-based ``is_sea`` (Phase 74's own convention),
# unlike PICKUP.X's own ``/S`` below (army-type-based, not terrain).
LEAVE_TEMPLATES: list[str] = [
    "< left = with [ in @.",
    "< dropped off = in @ for [.",
    "< ordered/Rdirected = to remain {encamped/Sanchored }in @ with [.",
    "< instructed/Rcommanded = to stay_behind/Rremain in @ with [.",
    "< transferred/Rassigned = to [ in @.",
]


def render_leave_unit(
    leader_name: str,
    province_name: str,
    army_type_name: str,
    commander_name: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders LEAVE.X's sentence for a single left-behind unit -- ``<``
    the leaving leader, ``@`` the province, ``=`` the army type's
    designation, ``[`` the leader (or unled fallback, Phase 420) the
    unit now serves under.
    """

    variant = pick_variant(LEAVE_TEMPLATES, rng)
    values = {"<": leader_name, "@": province_name, "=": army_type_name, "[": commander_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


def describe_leave(
    result: ArmyListExecutionResult,
    state: GameState,
    *,
    leader_name: str,
    province: ProvinceState,
    rng: random.Random,
) -> list[str]:
    """Assembles one LEAVE.X sentence per ``result.succeeded`` army id
    (Phase 420) -- ``result.skipped`` (army not found) has no sourced
    narrative, same "no source, no guess" stance as ``describe_recruit()``.

    ``[`` for an unled army (``ArmyListRequest.target_leader_id is
    None``) resolves via ``_unled_army_commander_name()``, shared with
    ``describe_recruit()`` -- ``_ALeave``'s own ``FD`` call is also at
    ``S_AA`` severity (``SAY.PAS``), so the exact same sourcing applies.
    """

    lines: list[str] = []
    province_name = _province_label(state, province.coord)
    is_sea = province.effective_terrain() is Terrain.SEA
    for army_id in result.succeeded:
        army = state.armies.get(army_id)
        if army is None:
            continue
        commander_name = _leader_name(state, army.commanded_by)
        if commander_name is None:
            commander_name = _unled_army_commander_name(province)
        army_type_name = ARMY_TYPE_DESIGNATION[army.army_type]
        lines.append(
            render_leave_unit(leader_name, province_name, army_type_name, commander_name, rng, is_sea=is_sea)
        )
    return lines


# HostAK/TP/PROSE/PICKUP.X -- one sentence per unit actually picked up
# (Phase 420). No ``[`` marker here at all -- Pick_Up's own new
# commander is always the acting leader itself (``>``), never
# ambiguous, unlike Recruit/Leave's unled fallback. ``/S`` alternates
# on whether the picked-up unit is itself a Fleet (``ArmyType.FLEET``
# is the project's only naval army type, Phase 5), not on province
# terrain -- a different use of the same marker than LEAVE.X's own.
PICKUP_TEMPLATES: list[str] = [
    "< picked up = in @.",
    "in @, < ordered/Rcommanded = to join forces with > army/Snavy.",
    "< strengthened/Raugmented > forces in @ with =.",
    "< added = to > host/Sfleet in @.",
]


def render_pickup_unit(
    leader_name: str, province_name: str, army_type_name: str, rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders PICKUP.X's sentence for a single picked-up unit -- ``<``
    the acting leader, ``@`` the province, ``=`` the army type's
    designation, ``>`` the leader's own possessive.
    """

    variant = pick_variant(PICKUP_TEMPLATES, rng)
    values = {"<": leader_name, "@": province_name, "=": army_type_name, ">": f"{leader_name}'s"}
    return render(variant, values, rng=rng, is_sea=is_sea)


def describe_pick_up(
    result: ArmyListExecutionResult, state: GameState, *, leader_name: str, province: ProvinceState, rng: random.Random
) -> list[str]:
    """Assembles one PICKUP.X sentence per ``result.succeeded`` army id
    (Phase 420) -- ``result.skipped`` (not found / not co-located) has
    no sourced narrative.
    """

    lines: list[str] = []
    province_name = _province_label(state, province.coord)
    for army_id in result.succeeded:
        army = state.armies.get(army_id)
        if army is None:
            continue
        is_sea = army.army_type is ArmyType.FLEET
        lines.append(
            render_pickup_unit(leader_name, province_name, ARMY_TYPE_DESIGNATION[army.army_type], rng, is_sea=is_sea)
        )
    return lines


# SAY.PAS _ADisb -- a single hardcoded template, not a PROSE file (Phase
# 420): "< disbanded =." No randomness at all (no /R, no {}), so
# render() is called directly rather than through pick_variant().
DISBAND_TEMPLATE = "< disbanded =."


def render_disband_unit(leader_name: str, army_type_name: str, rng: random.Random) -> str:
    """Renders ``_ADisb``'s sentence for a single disbanded unit."""

    return render(DISBAND_TEMPLATE, {"<": leader_name, "=": army_type_name}, rng=rng)


def describe_disband(
    result: ArmyListExecutionResult, state: GameState, *, leader_name: str, rng: random.Random
) -> list[str]:
    """Assembles one ``_ADisb`` sentence per ``result.succeeded`` army id
    (Phase 420). Unlike Leave/Pick_Up, Disband's own template needs no
    province or commander data at all, so it's the only one of the
    three that doesn't take a ``province`` argument.
    """

    lines: list[str] = []
    for army_id in result.succeeded:
        army = state.armies.get(army_id)
        if army is None:
            continue
        lines.append(render_disband_unit(leader_name, ARMY_TYPE_DESIGNATION[army.army_type], rng))
    return lines


# SAY.PAS _LDefend -- a single hardcoded template, not a PROSE file
# (Phase 421, same shape as _ADisb's own Phase 420 precedent): "<
# prepared > armies/Sforces to defend @ and the surrounding
# provinces." One /S alternation, no /R, no {} -- one rng draw at most
# (none at all, since /S never consumes one), so render() is called
# directly rather than through pick_variant(). ``is_sea`` resolves
# from the defended province's own terrain, this project's established
# Phase 74 convention for a bare /S marker with no other precedent
# (the same reading LEAVE.X's own {encamped/Sanchored } already got in
# Phase 420) -- not independently confirmed against a real defended-sea
# -province sample, since none exists in this project's fixture data.
DEFEND_TEMPLATE = "< prepared > armies/Sforces to defend @ and the surrounding provinces."


def render_defend(leader_name: str, province_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders ``_LDefend``'s sentence for a Defend order."""

    values = {"<": leader_name, ">": f"{leader_name}'s", "@": province_name}
    return render(DEFEND_TEMPLATE, values, rng=rng, is_sea=is_sea)


def describe_defend(state: GameState, *, leader_name: str, province: ProvinceState, rng: random.Random) -> str:
    """Assembles the ``_LDefend`` order-confirmation sentence (Phase 421).

    ``@`` is the defending leader's own current province -- the same
    basis ``turn/defend_execution.py defend_coverage_area()`` already
    uses for the real reinforcement mechanic (every neighbor of the
    leader's own location), not ``DefendRequest.target_province``
    (confirmed unused by that function, so resolving and narrating it
    here would be guessing at data the real mechanic never reads).

    **Deliberately not attempted here**: ``_LSplit``/``_LRemain``
    (splitting or concentrating coverage across two provinces -- blocked
    by ``DefendRequest.target_province``'s own confirmed-unconvertible
    raw int, see ``turn/aspy_defend_decode.py``'s docstring) and
    ``_ADefend`` (which armies actually got left/committed as
    reinforcement, via a ``^L=`` list marker -- an ambiguous trigger not
    confirmed to correspond to any data this project currently derives).
    ``_LHearInv`` (a covered leader learning of a distant attack) is
    narrated separately by ``describe_defend_reinforcement()`` below
    (Phase 422), once real per-leader reinforcement outcome data became
    available via ``turn/turn_processor.py``'s ``DefendReinforcement``.
    """

    province_name = _province_label(state, province.coord)
    is_sea = province.effective_terrain() is Terrain.SEA
    return render_defend(leader_name, province_name, rng, is_sea=is_sea)


# SAY.PAS _LHearInv: "<, responsible for the defense of @, learned/Rgot_wind
# of an enemy attack/Rmove on ^S." Two /R alternations ("learned/Rgot_wind",
# "attack/Rmove"), no /S, no {}, no pick_variant() -- two rng draws, same
# render() convention as DEFEND_TEMPLATE above.
DEFEND_REINFORCEMENT_TEMPLATE = (
    "<, responsible for the defense of @, learned/Rgot_wind of an enemy attack/Rmove on ^S."
)


def render_defend_reinforcement(
    defender_name: str, origin_name: str, target_name: str, rng: random.Random
) -> str:
    """Renders ``_LHearInv``'s sentence for a Defend reinforcement (Phase 422)."""

    values = {"<": defender_name, "@": origin_name, "^S": target_name}
    return render(DEFEND_REINFORCEMENT_TEMPLATE, values, rng=rng)


def describe_defend_reinforcement(
    result: DefendReinforcement, state: GameState, *, defender_name: str, rng: random.Random
) -> str:
    """Assembles the ``_LHearInv`` sentence for a real Defend reinforcement
    (Phase 422) -- ``result.origin`` is ``@`` (the defender's own province,
    where they were standing by), ``result.target`` is ``^S`` (the invaded
    province they relocated to cover), both resolved via ``turn/
    turn_processor.py _apply_defend_reinforcements()``'s real outcome data.
    """

    origin_name = _province_label(state, result.origin)
    target_name = _province_label(state, result.target)
    return render_defend_reinforcement(defender_name, origin_name, target_name, rng)


def describe_move(
    result: MoveExecutionResult, state: GameState, *, character_name: str, board_width: int, rng: random.Random
) -> str | None:
    """Assembles MARCH.X's sentence for a completed Move (Phase 421),
    wiring the already-built ``render_march()`` (Phase 104) into a real
    caller for the first time -- it existed but was never reached from
    ``describe_turn_results()``, the same kind of gap Phase 214 already
    closed for Trade.

    Returns ``None`` for a Move that didn't actually relocate the
    leader (``result.moved`` is ``False``, or ``result.new_location``
    is unset -- e.g. an illegal/blocked Move, which has its own
    separate narrative templates, Phase 127) -- no sourced sentence
    exists for "you tried to move and failed" beyond those.
    ``province_number`` is ``PROSE.TXT``'s own ``^P`` marker, the same
    ``str(encode_hex_number(...))`` convention ``describe_rumor()``'s
    own Phase 247 precedent already established.
    """

    if not result.moved or result.new_location is None:
        return None
    province = state.provinces.get(result.new_location)
    province_name = _province_label(state, result.new_location)
    province_number = str(encode_hex_number(result.new_location, board_width))
    is_sea = province is not None and province.effective_terrain() is Terrain.SEA
    return render_march(character_name, province_name, province_number, rng, is_sea=is_sea)


# HostAK/TP/PROSE/ALLY.X -- a successful Ally proposal. See module
# docstring's Phase 116 addendum.
_ALLY_TEMPLATES: list[str] = [
    "< urged/Rasked [3 to improve {diplomatic }relations with > "
    "{great }Kingdom, speaking at_length/Reloquently of the great "
    "advantages/Rbenefits of such ^A agreement.{After some "
    "deliberation, }the offer/Rproposal was wisely/Rgraciously "
    "accepted by [.",
    "< {formally }proposed ^A treaty with [{'s Kingdom}, and the "
    "{magnanimous }offer was {graciously and wisely }accepted.{May "
    "the treaty between < and [3 last forever/Rfor_eternity!}",
]


def render_ally_proposed(character_name: str, king_name: str, rng: random.Random) -> str:
    """Renders ALLY.X's sentence for a successful Ally proposal. Both
    ``[3`` and ``[`` refer to the same target King within a single
    template -- both substituted with ``king_name``.
    """

    variant = pick_variant(_ALLY_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[3": king_name,
        "[": king_name,
        ">": f"{character_name}'s",
    }
    return render(variant, values, rng=rng)


# HostAK/TP/SAY.PAS _LATreat -- a single, real, hardcoded template (no
# file), an already-allied notice distinct from render_ally_proposed()'s
# own first-time proposal. See module docstring's Phase 116 addendum.
ALREADY_ALLIED_TEMPLATE = "< treated with > ally [3."


def render_already_allied(character_name: str, king_name: str, rng: random.Random) -> str:
    """Renders ``_LATreat``'s repeat-turn "we already have a treaty"
    notice.
    """

    values = {"<": character_name, ">": f"{character_name}'s", "[3": king_name}
    return render(ALREADY_ALLIED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LRefA -- a single, real, hardcoded entry made of
# two separate Say(...) calls (no file). See module docstring's Phase
# 116 addendum.
_ALLY_REFUSED_TEMPLATES = (
    "< Treated with [3, but [1 did not respond/Rreact {favorably }to "
    "> friendly/Ramicable noises/Rovertures.",
    "it is hoped that next year, both Kings will see the wisdom of Treating.",
)


def render_ally_refused(character_name: str, king_name: str, rng: random.Random) -> str:
    """Renders ``_LRefA``'s two-sentence entry for a refused Ally
    proposal, concatenated with no separator -- matching Turbo Pascal's
    own sequential ``Say(...)`` writes (see module docstring).
    """

    values = {
        "<": character_name,
        "[3": king_name,
        "[1": king_name,
        ">": f"{character_name}'s",
    }
    first = render(_ALLY_REFUSED_TEMPLATES[0], values, rng=rng)
    second = render(_ALLY_REFUSED_TEMPLATES[1], values, rng=rng)
    return first + second


# HostAK/TP/PROSE/TAKEG.X -- a successful gold theft. See module
# docstring's Phase 117 addendum.
_TAKEG_TEMPLATES: list[str] = [
    "< stole # gold from [.",
    "< stole/Rpilfered # gold from ] treasure chest.",
    "< robbed [ of # gold{ while [1 was sleeping}.",
]


def render_take_gold(character_name: str, victim_name: str, gold_amount: int, rng: random.Random) -> str:
    """Renders TAKEG.X's sentence for a successful gold theft."""

    variant = pick_variant(_TAKEG_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": victim_name,
        "[1": victim_name,
        "]": f"{victim_name}'s",
        "#": str(gold_amount),
    }
    return render(variant, values, rng=rng)


# HostAK/TP/SAY.PAS _LRans -- a single, real, hardcoded entry made of
# two separate Say(...) calls (no file), a failed Steal attempt: caught
# red-handed, then ransomed. See module docstring's Phase 119 addendum.
_STEAL_RANSOM_TEMPLATES = (
    "[1 caught <2 red-handed while < was rummaging through ] things "
    "in a bungled attempt at thievery.",
    "[1 forced <2 to pay [ half > treasury in ransom before letting him go.",
)


def render_steal_caught_and_ransomed(catcher_name: str, thief_name: str, rng: random.Random) -> str:
    """Renders ``_LRans``'s two-sentence entry for a failed Steal
    attempt, concatenated with no separator (see module docstring).
    """

    values = {
        "[": catcher_name,
        "[1": catcher_name,
        "<": thief_name,
        "<2": thief_name,
        "]": f"{catcher_name}'s",
        ">": f"{thief_name}'s",
    }
    first = render(_STEAL_RANSOM_TEMPLATES[0], values, rng=rng)
    second = render(_STEAL_RANSOM_TEMPLATES[1], values, rng=rng)
    return first + second


# HostAK/TP/SAY.PAS _LBurn -- a single, real, hardcoded template (no
# file), immediately before _LInher in RUMORS.PAS's own CONST block.
# See module docstring's Phase 119 addendum.
FUNERAL_PYRE_TEMPLATE = "] possessions were burned with [3 on the funeral pyre."


def render_funeral_pyre(deceased_name: str, mourner_name: str, rng: random.Random) -> str:
    """Renders ``_LBurn``'s sentence for a funeral pyre."""

    values = {"]": f"{deceased_name}'s", "[3": mourner_name}
    return render(FUNERAL_PYRE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LInher -- a single, real, hardcoded template (no
# file), the confirmed ELSE branch. See module docstring's Phase 118
# addendum for the THEN branch, unblocked there.
INHERIT_TEMPLATE = "< inherited/Rgained the \\."


def render_inherit(character_name: str, item_name: str, rng: random.Random) -> str:
    """Renders ``_LInher``'s ELSE-branch sentence for inheriting a
    single magic item.
    """

    values = {"<": character_name, "\\": item_name}
    return render(INHERIT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LInher -- the THEN branch (``_attl = _defl``).
# Deliberately left blocked in Phase 117 (before report/prose.py's own
# ^L list-insertion capability existed); unblocked in Phase 118.
INHERIT_AS_HEIR_TEMPLATE = "The heir of < inherited/Rgained the ^L\\."


def render_inherit_as_heir(character_name: str, item_names: list[str], rng: random.Random) -> str:
    """Renders ``_LInher``'s THEN-branch sentence, for inheriting
    *multiple* magic items as an heir -- ``item_names`` is
    ``PROSE.TXT``'s own ``\\`` marker ("Magic Item"), joined via
    ``report/prose.py``'s ``^L`` list insertion (Phase 118).
    """

    values = {"<": character_name}
    return render(INHERIT_AS_HEIR_TEMPLATE, values, rng=rng, lists={"\\": item_names})


# HostAK/TP/SAY.PAS _MGain -- a single, real, hardcoded template (no
# file), real and dispatched immediately alongside _LInher/_LWill.
# Deliberately left blocked in Phase 117; unblocked in Phase 118.
TAKE_ITEMS_TEMPLATE = "< took the ^L\\."


def render_take_items(character_name: str, item_names: list[str], rng: random.Random) -> str:
    """Renders ``_MGain``'s sentence for taking *multiple* magic items
    -- ``item_names`` is ``PROSE.TXT``'s own ``\\`` marker, joined via
    ``report/prose.py``'s ``^L`` list insertion (Phase 118).
    """

    values = {"<": character_name}
    return render(TAKE_ITEMS_TEMPLATE, values, rng=rng, lists={"\\": item_names})


# HostAK/TP/SAY.PAS _LWill -- a single, real, hardcoded template (no
# file). See module docstring's Phase 117 addendum.
WILL_TEMPLATE = "['s will left {all }] {worldly }possessions to ] compatriots/Rfellow_adventurers."


def render_will(deceased_name: str, rng: random.Random) -> str:
    """Renders ``_LWill``'s sentence for the deceased's will being read."""

    values = {"[": deceased_name, "]": f"{deceased_name}'s"}
    return render(WILL_TEMPLATE, values, rng=rng)


# HostAK/TP/PROSE/MARCH.X -- the Move action's own report line. See
# module docstring's Phase 104 addendum for why this uses pick_variant
# (a small `dex` value, RUMORS.PAS FD's own per-character-seed pseudo-
# random scheme) rather than a deterministic index.
_MARCH_TEMPLATES: list[str] = [
    "< marched_on/Ssailed_into @ ^P with > {formidable }command/Rforces.",
    "< {boldly }marched/Ssailed > forces/Rcommand into @ ^P.",
    "< moved into @ ^P with > {redoubtable/Rhigh-spirited }army/SFleet.",
]


def render_march(
    character_name: str,
    province_name: str,
    province_number: str,
    rng: random.Random,
    *,
    is_sea: bool = False,
) -> str:
    """Renders MARCH.X's sentence for a Move -- ``province_number`` is
    ``PROSE.TXT``'s own ``^P`` marker ("Province number", e.g.
    ``"0304"``), distinct from ``province_name`` (``@``). ``is_sea``
    (Phase 74) resolves the "/S" marker every variant here carries.
    """

    variant = pick_variant(_MARCH_TEMPLATES, rng)
    values = {
        "<": character_name,
        "@": province_name,
        "^P": province_number,
        ">": f"{character_name}'s",
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/SAY.PAS _LCMarch -- a single, real, hardcoded template (no
# file), a defensive Move (reinforcing a threatened province), distinct
# from the regular Move narrative above. See module docstring's Phase
# 120 addendum.
DEFENSIVE_MARCH_TEMPLATE = "< marched into @ from ^S to defend @ against its would-be conquerors."


def render_defensive_march(
    character_name: str, province_name: str, origin_province_name: str, rng: random.Random
) -> str:
    """Renders ``_LCMarch``'s sentence for a defensive Move. ``^S``
    (Province name #2) is the origin province.
    """

    values = {"<": character_name, "@": province_name, "^S": origin_province_name}
    return render(DEFENSIVE_MARCH_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LCatch -- a single, real, hardcoded template (no
# file), the Pursue/Trail catch-up moment. See module docstring's
# Phase 120 addendum.
CAUGHT_UP_TEMPLATE = "< caught up with [ in @."


def render_caught_up(character_name: str, target_name: str, province_name: str, rng: random.Random) -> str:
    """Renders ``_LCatch``'s sentence for a Pursue/Trail catch-up."""

    values = {"<": character_name, "[": target_name, "@": province_name}
    return render(CAUGHT_UP_TEMPLATE, values, rng=rng)


def describe_pursue(
    result: PursueExecutionResult,
    *,
    pursuer_name: str,
    target_name: str,
    province_name: str,
    rng: random.Random,
) -> str | None:
    """Compose Pursue's own turn-report line from an already-computed
    ``PursueExecutionResult`` (Phase 51/53), sixth slice of the
    report-assembler thread.

    Renders ``render_caught_up()`` (``_LCatch``, confirmed a shared
    Pursue/Trail sentence by its own docstring) whenever
    ``result.caught_up`` is ``True`` -- covering all three real
    catch-up shapes this project resolves (an army-vs-army battle via
    ``result.battle_report``, an armyless personal duel via
    ``result.combat_occurred``/``winner_leader_id``, or no combat intent
    at all): the catch-up moment itself is a single narrative event, the
    same "no source ties two moments into one combined sentence, the
    caller composes" stance already taken for the Ice-Suspend cluster
    (Phase 123) -- a caller with a real ``battle_report`` composes
    further with ``describe_battle()`` separately, the same
    caller-composes-the-sequence precedent, rather than this function
    reaching into that unrelated subsystem's own army-naming
    requirements.

    Returns ``None`` when ``result.caught_up`` is ``False`` (a failed
    catch-up roll, an army-leading mismatch, or the pursuer/target not
    found) -- no catch-up happened, so there is nothing to narrate.
    """

    if not result.caught_up:
        return None
    return render_caught_up(pursuer_name, target_name, province_name, rng)


def describe_encounter_combat(
    result: ChallengeExecutionResult | PursueExecutionResult,
    *,
    a_leader_id: int,
    a_name: str,
    b_name: str,
    rng: random.Random,
    is_sea: bool = False,
) -> list[str]:
    """Phase 417: the personal-combat narration Challenge's and Pursue's
    own armyless-duel case have had zero narration for since either was
    first implemented (Phase 50/51) -- `ChallengeCombatOutcome`/
    `ChallengeExecutionResult`/`PursueExecutionResult` all gained `fire_
    arrow_shots`/`melee_swings` fields this phase, mirroring `turn/
    search_execution.py SearchExecutionResult`'s own Phase 175/415/416
    fields, but Search's own `describe_search()` can't be reused directly
    -- Challenge/Pursue's opponent is always another character, never a
    monster, so there's no species-flavor branching to thread through,
    and `a`/`b` name generically rather than "leader"/"guardian".

    Shared by `describe_challenge()` below and `describe_turn_results()`'s
    own `ActionCode.PURSUE` branch (which still opens with `describe_
    pursue()`'s own `_LCatch` sentence separately, unchanged) -- the same
    "shared field names, no isinstance check" reuse `describe_steal()`
    already established for these same two result types (Phase 306).

    Returns `[]` outright when `result.combat_occurred` is `False` --
    covers every administrative rejection (not accepted, not co-located,
    refused) *and* a genuinely peaceful accepted plan in one check, since
    every one of `execute_challenge()`/`execute_pursue()`'s own early
    returns before real combat leaves `combat_occurred` at its `False`
    default. No sourced sentence exists for a refused/peaceful encounter
    either way (the same "no source, no guess" policy `describe_give()`
    already states), and a successful Charm/Augur-first flee
    (`result.fled`) has no sourced sentence of its own -- only the real
    swings that happened before it are narrated, not the flee itself.

    Order: `describe_steal()`'s own sub-event line (if any) first --
    Steal, when present, always happens *before* whatever combat follows
    getting caught, chronologically -- then every Fire Arrow shot, then
    every Melee swing (both in `result` order, i.e. chronological), then
    `render_mortally_wounded()` if `result.loser_killed` (the same
    MORTWOUN.X sentence every other personal-combat death already uses),
    then (Phase 611) `render_character_death()` -- HORDEATH.X's own
    generic closing beat, sourced (`SAY.PAS:429-432 _LDies`) as firing
    for *any* real leader death right after its own cause-specific
    sentence, the same shared-trailer role `_LSucc` fills for
    succession. `a_leader_id` resolves which of `a_name`/`b_name` is the loser from
    `result.loser_leader_id` -- `resolve_challenge_combat()`'s own "a" is
    always the challenger/pursuer, "b" always the target, so `a_name`/
    `b_name` here must be supplied in that same order.
    """

    if not result.combat_occurred:
        return []

    lines: list[str] = []
    steal_line = describe_steal(result, thief_name=a_name, victim_name=b_name, rng=rng)
    if steal_line is not None:
        lines.append(steal_line)

    for shot in result.fire_arrow_shots:
        attacker_name, defender_name = (a_name, b_name) if shot.shooter == "a" else (b_name, a_name)
        attack_line = render_fire_arrow_attack(attacker_name, defender_name, rng)
        attack_line += (
            render_attack_hit(defender_name, shot.damage, rng)
            if shot.hit
            else render_attack_missed(attacker_name, defender_name, "arrow", rng, is_sea=is_sea)
        )
        lines.append(attack_line)

    for swing in result.melee_swings:
        attacker_name, defender_name = (a_name, b_name) if swing.attacker == "a" else (b_name, a_name)
        attack_line = render_melee_attack(attacker_name, defender_name, _MELEE_ATTACK_METHOD, rng)
        attack_line += (
            render_attack_hit(defender_name, swing.damage, rng)
            if swing.hit
            else render_attack_missed(attacker_name, defender_name, "blade", rng, is_sea=is_sea)
        )
        lines.append(attack_line)

    if result.loser_killed:
        loser_name = a_name if result.loser_leader_id == a_leader_id else b_name
        lines.append(render_mortally_wounded(loser_name, rng, is_sea=is_sea))
        lines.append(render_character_death(loser_name, rng))

    return lines


# HostAK/TP/PROSE/ENCATT.X -- very likely Challenge's own opening
# sentence, "searching for the target" before whatever encounter/combat
# follows (Phase 597). `SAY.PAS:677 _LChall: FD('encatt',S_PCom,9)` sits
# in the same personal-combat outcome cluster as `_LSwing`/`_LFlee`/
# `_LCow`/etc. (most already wired in this project), and `describe_
# challenge()`'s own combat narration below has no "opening" beat of its
# own -- but unlike Phase 595's `HIREMERC.X` (confirmed a real sibling
# via adjacent `RUMORS.PAS` constants *and* an already-tracked model
# field), nothing in the available `.PAS` corpus confirms `_LChall`
# fires unconditionally on every Challenge, so `describe_challenge()`
# itself is left unmodified -- sourced and render-tested, not wired.
_ENCATT_TEMPLATES: list[str] = [
    "< searched {all }throughout @ for {some sign of }[.",
    "< looked {around }for [ in @.",
    "< searched/Rlooked for [ in the bars/Rtaverns and whorehouses/Rinns of @.",
    "< scouted {around }for [ in {the province of }@.",
]


def render_challenge_search(searcher_name: str, target_name: str, province_name: str, rng: random.Random) -> str:
    """Renders ENCATT.X's sentence for searching a province for a
    Challenge target (Phase 597) -- see the module comment above for why
    it isn't wired into ``describe_challenge()``.
    """

    variant = pick_variant(_ENCATT_TEMPLATES, rng)
    values = {"<": searcher_name, "[": target_name, "@": province_name}
    return render(variant, values, rng=rng)


def describe_challenge(
    result: ChallengeExecutionResult,
    *,
    challenger_leader_id: int,
    challenger_name: str,
    target_name: str,
    rng: random.Random,
    is_sea: bool = False,
) -> list[str]:
    """Assembles Challenge's own turn-report lines from an already-computed
    ``ChallengeExecutionResult`` (``turn/challenge_execution.py
    execute_challenge()``, Phase 50/290/292/305/306/417) -- Challenge's
    own report presence, from zero: `describe_turn_results()` never had
    an ``ActionCode.CHALLENGE`` branch before this phase, since
    ``ChallengeExecutionResult`` had no ``request`` field for it to
    resolve ``target_name`` from at all (see this dataclass's own Phase
    417 addendum, mirroring ``PursueExecutionResult.request``'s own
    Phase 213 field).

    A thin wrapper over ``describe_encounter_combat()`` (this module's
    own shared Challenge/Pursue personal-combat narration) -- see that
    function's own docstring for the full composition order and the
    "no source, no guess" reasoning behind every case it renders nothing
    for (a refused/peaceful encounter, a successful flee's own final
    beat).
    """

    return describe_encounter_combat(
        result,
        a_leader_id=challenger_leader_id,
        a_name=challenger_name,
        b_name=target_name,
        rng=rng,
        is_sea=is_sea,
    )


def describe_trail(
    result: TrailExecutionResult,
    *,
    trailer_name: str,
    target_name: str,
    province_name: str,
    rng: random.Random,
) -> str | None:
    """Compose Trail's own turn-report line from an already-computed
    ``TrailExecutionResult`` (Phase 52), sharing ``render_caught_up()``
    with ``describe_pursue()`` above -- the same ``_LCatch`` sentence,
    confirmed a real Pursue/Trail sibling by its own docstring.

    Returns ``None`` when ``result.spied_on`` is ``False`` (a failed
    catch-up roll, Trail's own no-army restriction rejecting the order,
    or the trailer/target not found).
    """

    if not result.spied_on:
        return None
    return render_caught_up(trailer_name, target_name, province_name, rng)


# Phase 212 -- [3.17]'s own intelligence payload (temper, alignment, race,
# treasures owned, armies led, and a King's finances/allies/controlled
# provinces) has no confirmed PROSE source anywhere in the available
# archive, unlike the SAY.PAS-sourced ASpy templates above. These eleven
# templates are project-original, written on direct user instruction
# ("Prosa originale del progetto") after confirming no source exists --
# see `turn/trail_execution.py`'s own module docstring for the data
# layer these narrate (Phases 159/164/165/166), already fully computed
# and simply never rendered before this phase.
TRAIL_TEMPER_TEMPLATE = "< learned that [ has temper |."
TRAIL_ALIGNMENT_TEMPLATE = "< learned that [ is | in alignment."
TRAIL_RACE_TEMPLATE = "< learned that [ is |."
TRAIL_TREASURES_TEMPLATE = "< learned that [ owns ^L^V."
TRAIL_NO_TREASURES_TEMPLATE = "< learned that [ owns no treasures."
TRAIL_ARMIES_LED_TEMPLATE = "< learned that [ leads ^L^V."
TRAIL_NO_ARMIES_LED_TEMPLATE = "< learned that [ leads no armies."
TRAIL_KING_FINANCES_TEMPLATE = "< learned that [ commands a treasury of # gold."
TRAIL_KING_ALLIES_TEMPLATE = "< learned that [ is allied with ^L^V."
TRAIL_KING_NO_ALLIES_TEMPLATE = "< learned that [ has no allies."
TRAIL_KING_PROVINCES_TEMPLATE = "< learned that [ controls ^L^V."
TRAIL_KING_NO_PROVINCES_TEMPLATE = "< learned that [ controls no provinces."


def render_trail_temper(trailer_name: str, target_name: str, temper_name: str, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": target_name, "|": temper_name}
    return render(TRAIL_TEMPER_TEMPLATE, values, rng=rng)


def render_trail_alignment(trailer_name: str, target_name: str, alignment_name: str, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": target_name, "|": alignment_name}
    return render(TRAIL_ALIGNMENT_TEMPLATE, values, rng=rng)


def render_trail_race(trailer_name: str, target_name: str, race_name: str, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": target_name, "|": race_name}
    return render(TRAIL_RACE_TEMPLATE, values, rng=rng)


def render_trail_treasures(
    trailer_name: str, target_name: str, treasure_names: list[str], rng: random.Random
) -> str:
    values = {"<": trailer_name, "[": target_name}
    return render(TRAIL_TREASURES_TEMPLATE, values, rng=rng, lists={"^V": treasure_names})


def render_trail_no_treasures(trailer_name: str, target_name: str, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": target_name}
    return render(TRAIL_NO_TREASURES_TEMPLATE, values, rng=rng)


def render_trail_armies_led(trailer_name: str, target_name: str, army_names: list[str], rng: random.Random) -> str:
    values = {"<": trailer_name, "[": target_name}
    return render(TRAIL_ARMIES_LED_TEMPLATE, values, rng=rng, lists={"^V": army_names})


def render_trail_no_armies_led(trailer_name: str, target_name: str, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": target_name}
    return render(TRAIL_NO_ARMIES_LED_TEMPLATE, values, rng=rng)


def render_trail_king_finances(trailer_name: str, king_name: str, treasury: int, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": king_name, "#": str(treasury)}
    return render(TRAIL_KING_FINANCES_TEMPLATE, values, rng=rng)


def render_trail_king_allies(trailer_name: str, king_name: str, ally_names: list[str], rng: random.Random) -> str:
    values = {"<": trailer_name, "[": king_name}
    return render(TRAIL_KING_ALLIES_TEMPLATE, values, rng=rng, lists={"^V": ally_names})


def render_trail_king_no_allies(trailer_name: str, king_name: str, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": king_name}
    return render(TRAIL_KING_NO_ALLIES_TEMPLATE, values, rng=rng)


def render_trail_king_provinces(
    trailer_name: str, king_name: str, province_names: list[str], rng: random.Random
) -> str:
    values = {"<": trailer_name, "[": king_name}
    return render(TRAIL_KING_PROVINCES_TEMPLATE, values, rng=rng, lists={"^V": province_names})


def render_trail_king_no_provinces(trailer_name: str, king_name: str, rng: random.Random) -> str:
    values = {"<": trailer_name, "[": king_name}
    return render(TRAIL_KING_NO_PROVINCES_TEMPLATE, values, rng=rng)


def _trail_army_name(state: GameState, army: ArmyState) -> str:
    """Same race-resolution shape as ``turn/aspy_execution.py
    _army_display_name()`` (Phase 212) -- kept as a separate, small
    duplicate rather than imported, the same "don't share a four-line
    helper across an unrelated module boundary" precedent
    ``_leader_combatant()`` already established (Phase 209/210's own
    module docstrings in ``turn/cast_execution.py``/``turn/
    search_execution.py``).
    """

    kingdom = state.kingdoms.get(army.kingdom_id) if army.kingdom_id is not None else None
    race = MONSTROUS_ARMY_RACE.get(army.army_type, kingdom.race if kingdom is not None else Race.HUMAN)
    return make_army_name(army.army_id, army.army_type, race)


def _province_label(state: GameState, coord: HexCoord) -> str:
    """Same ``ProvinceState.name`` else raw-coordinate fallback
    ``describe_armies_report()``'s own Phase 158 note already
    established, kept inline there since it only has the one call site.
    """

    province = state.provinces.get(coord)
    if province is not None and province.name:
        return province.name
    return f"({coord.x}, {coord.y})"


def describe_trail_intelligence(
    result: TrailExecutionResult, *, state: GameState, trailer_name: str, target_name: str, rng: random.Random
) -> list[str]:
    """Renders [3.17]'s own intelligence payload from an already-computed
    ``TrailExecutionResult`` (``turn/trail_execution.py execute_trail()``,
    Phases 52/159/164/165/166) -- a separate function from
    ``describe_trail()`` above (which only narrates the catch-up moment
    itself, ``_LCatch``) rather than folding this in, so
    ``describe_trail()``'s own existing signature/callers stay
    untouched.

    Returns ``[]`` when ``result.spied_on`` is ``False`` -- nothing was
    learned. Each of the five sourced fields ([3.17]'s "Actions" stays
    unrendered -- see ``turn/trail_execution.py``'s own module docstring
    for why it's structurally unbuildable) renders exactly one line,
    skipped only when the field itself is ``None`` (temper/alignment/
    race, the same "no data recorded" convention the data layer already
    uses) -- the list-shaped fields (treasures/armies led) always render
    one line, choosing between a populated-list template and a
    dedicated "none" template rather than skipping silently, since an
    empty list is itself a real, learned fact ("Trailer learned Target
    owns nothing"), not missing data.

    ``result.king_intelligence`` (only set when the target is a King)
    adds up to three further lines the same way: finances always
    renders (a treasury of 0 gold is still a real fact); allies and
    controlled provinces each choose between their populated/"none"
    template pair. Kingdom names are resolved via
    ``GameState.kingdoms``; province names via ``ProvinceState.name``,
    falling back to a raw coordinate the same way
    ``describe_armies_report()``'s own Phase 158 precedent already
    does for an unnamed province.
    """

    if not result.spied_on:
        return []

    lines: list[str] = []
    if result.temper is not None:
        lines.append(render_trail_temper(trailer_name, target_name, TEMPER_NAME[result.temper], rng))
    if result.alignment is not None:
        lines.append(render_trail_alignment(trailer_name, target_name, result.alignment.value, rng))
    if result.race is not None:
        lines.append(render_trail_race(trailer_name, target_name, RACE_NAME[result.race], rng))

    treasure_names = [TREASURE_NAME[item.treasure] for item in result.treasures_owned]
    if treasure_names:
        lines.append(render_trail_treasures(trailer_name, target_name, treasure_names, rng))
    else:
        lines.append(render_trail_no_treasures(trailer_name, target_name, rng))

    army_names = [_trail_army_name(state, army) for army in result.armies_led]
    if army_names:
        lines.append(render_trail_armies_led(trailer_name, target_name, army_names, rng))
    else:
        lines.append(render_trail_no_armies_led(trailer_name, target_name, rng))

    king = result.king_intelligence
    if king is not None:
        lines.append(render_trail_king_finances(trailer_name, target_name, king.treasury, rng))

        ally_names = [
            state.kingdoms[kid].name for kid in king.allied_kingdom_ids if kid in state.kingdoms
        ]
        if ally_names:
            lines.append(render_trail_king_allies(trailer_name, target_name, ally_names, rng))
        else:
            lines.append(render_trail_king_no_allies(trailer_name, target_name, rng))

        province_names = [_province_label(state, coord) for coord in king.controlled_provinces]
        if province_names:
            lines.append(render_trail_king_provinces(trailer_name, target_name, province_names, rng))
        else:
            lines.append(render_trail_king_no_provinces(trailer_name, target_name, rng))

    return lines


# The Cast/Use_MI spells whose own SPELL_CAST_ANNOUNCEMENT entry needs a
# target *character* (see render_cast_announcement()'s own
# _CAST_ANNOUNCEMENT_TARGET_SPELLS) -- the only CastRequest.target shape
# describe_turn_results() below can safely resolve automatically via
# state.leaders, since CastRequest.target's own meaning (character id,
# province id, or unused) is spell-dependent and this project has no
# blanket way to tell them apart without checking spell membership first.
_AUTO_RESOLVABLE_CAST_TARGET_SPELLS = frozenset(
    {Spell.KILL_ENEMY, Spell.RESURRECTION, Spell.ILLUS_ARMIES, Spell.ORATORY, Spell.CHARM}
)


def _leader_name(state: GameState, leader_id: int | None) -> str | None:
    """Resolves a leader's display name for narration, whether they're
    still alive or died earlier in the same turn (Phase 612 fix).

    `describe_turn_results()` composes every action's narration only
    after `run_turn()` has fully mutated `state` -- including every
    `GameState.remove_leader()` call for that turn's own deaths -- so an
    acting leader (or their target) who died as a *result* of their own
    action is already gone from `state.leaders` by the time this runs.
    Before this fix, that made the whole entry's `caster_name`/
    `target_name` lookup silently return `None`, which every calling
    branch's own early-return guard then read as "can't narrate this,"
    dropping the ENTIRE action's narration -- not just the death, but
    every real, already-happened sentence before it too (confirmed via
    a direct reproduction: a Challenger who loses and dies got zero
    turn-report lines at all). `remove_leader()` archives the exact same
    `LeaderState` object into `state.dead_leaders` (Phase 59, kept there
    so a later Resurrection has something to revive) -- its `.name`
    field is never touched by death, so falling back to that archive
    here recovers the real name with no invented text, the same "the
    fact already exists in state, just check the right dict" fix shape
    as every other real gap this project closes.
    """

    if leader_id is None:
        return None
    leader = state.leaders.get(leader_id) or state.dead_leaders.get(leader_id)
    return leader.name if leader is not None else None


def _leader_location(state: GameState, leader_id: int) -> HexCoord | None:
    """Same alive-or-dead fallback as ``_leader_name()`` (Phase 612), for
    the 3 branches below (Pursue/Challenge/Trail) that need the acting
    leader's own province for ``is_sea``/`describe_pursue()`/`describe_
    trail()`'s own ``province_name``. `remove_leader()` never touches
    `.location` -- a dead leader keeps the province they died in, which
    is exactly the right value for narrating combat that happened
    there. Without this, a raw ``state.leaders[entry.leader_id]``
    subscript (the pre-Phase-612 code at all 3 sites) raised a bare
    ``KeyError`` the instant `_leader_name()`'s own fallback let
    execution reach this far for an acting leader who died in their own
    action -- previously unreachable in practice only because `_leader_
    name()` itself returned `None` first and the caller already
    `continue`d before ever getting here.
    """

    leader = state.leaders.get(leader_id) or state.dead_leaders.get(leader_id)
    return leader.location if leader is not None else None


def describe_turn_results(
    results: list[PhaseDispatchResult],
    state: GameState,
    rng: random.Random,
    *,
    ability_names: dict[Ability, str] | None = None,
    board_width: int | None = None,
) -> list[str]:
    """Walks ``turn/turn_processor.py run_turn()``'s own output (a flat
    ``list[PhaseDispatchResult]``, one entry per dispatched phase) and
    calls the matching ``describe_*`` composer for each entry it can,
    skipping the rest -- the first real caller of any ``describe_*``
    function in this project (Phases 142-147 built nine composers, but
    none had ever been wired to a real turn until now).

    **Character/leader names are always resolved directly from
    ``state.leaders[leader_id].name``** -- confirmed always available,
    no gap here (unlike province/army naming, Phase 149/150).

    **Confirmed, not guessed, why several actions aren't wired here at
    all**: `HIRE`/`FIRE` (`describe_hire()`/`describe_fire()`) and
    `CAST`/`USE_MI`'s wand path (`describe_cast()`/`describe_use_mi()`,
    for the 5 character-targeted spells in
    `_AUTO_RESOLVABLE_CAST_TARGET_SPELLS`) are wired because their own
    result type retains a real target-leader id (`HireExecutionResult
    .request.hero_id`, `FireExecutionResult.request.hero_id`,
    `CastExecutionResult.request.target`) this function can resolve via
    `state.leaders`. `PRACTICE` needs a caller-supplied ``ability_names``
    entry (`PracticeExecutionResult.ability` is real, but no sourced
    `Ability` display-name table exists in this project yet -- see
    `models/army_naming.py`'s own Phase 149 precedent for why an
    unverified table isn't invented here either); its own "tutored"
    branch never fires through this function regardless, since
    `PracticeExecutionResult` has no field recording who tutored
    (Phase 144's own docstring).

    **Phase 213 closes `PURSUE`/`TRAIL`/`SEARCH`/`ASPY`** -- the four
    actions this docstring previously said were unwireable because
    their own result types carried no target/feature id at all.
    `PursueExecutionResult`/`TrailExecutionResult`/
    `SearchExecutionResult` each gained a `request` field (Phase 213),
    stamped by `plan_dispatch.py`'s own `_dispatch_pursue()`/
    `_dispatch_trail()`/`_dispatch_search()` -- the one real call site
    every actual turn passes through -- rather than by the `execute_*()`
    functions themselves (see those dispatchers' own Phase 213 notes for
    why: avoids touching a combined ~30 early-return sites across three
    modules for a field only this composer needs). A direct
    `execute_pursue()`/`execute_trail()`/`execute_search()` call (every
    existing unit test included) still gets `request=None`, so those
    entries are skipped here (`continue`), not crashed on.
    `TRAIL`'s own catch-up line (`describe_trail()`) and its
    intelligence payload (`describe_trail_intelligence()`, Phase 212)
    both render together, in that order. `ASPY` needed no such field --
    `SpyReport.province` (a real `HexCoord`) was already enough.
    `SEARCH`'s own `feature_name` has no sourced display-name system at
    all (`Feature` carries no `name` field, unlike `ProvinceState`) --
    resolved via a bare coordinate, the same fallback
    `_province_label()`'s own Phase 158/212 precedent already
    established for an unnamed province, not a new invented rule.

    **`TRADE` was closed by Phase 214** (this paragraph's original "stays
    unwired" claim went stale then and was never corrected until Phase
    418): `TradeExecutionResult` gained a `request` field and a real
    `item: ItemInstance | None` field (Phase 214), so the branch below
    resolves `item_name` itself via `TREASURE_NAME[entry.result.item
    .treasure]` and calls `describe_give()` directly -- see that
    function's own docstring for the full item/gold/failure-reason
    breakdown.
    `describe_battle()` stays out of this dispatch -- it needs a
    `BattleReport` and multi-army name maps no `PhaseDispatchResult`
    alone carries. Province/terrain/army-list Cast spells and Use_MI's
    skill-book path are skipped the same way, for the same reason Phase
    150 already established: no general province-naming system exists.

    **Phase 247 closes `EXPLORE` and rumor narration**, the two
    `describe_*` composers (Phase 244/245) built but never reached from
    here. `EXPLORE`'s own branch renders `describe_feature_discovery()`
    for every `ExploreResult.discovered_features` entry -- the province
    is always the discoverer's own current one, so `feature.coord`
    resolves it directly.

    **Rumors don't attach to any one `PhaseDispatchResult` entry** --
    `turn/rumor.py resolve_rumor_generation()` is a side effect of
    `dispatch_phase()` itself (Phase 243), decoupled from whatever
    action-specific result it returns. Rendered as a separate pass
    after the main walk instead: for every distinct `leader_id` present
    in `results`, every `Rumor` in `state.rumors_heard_by(leader.
    kingdom_id)` whose own `leader_id` (Phase 247) matches gets
    narrated via `describe_rumor()`. **Opt-in via `board_width`**
    (`None` by default) -- `describe_rumor()` needs it to encode the
    described province's raw hex number, and every pre-Phase-247 caller
    (this whole module's own test suite included) has no board width to
    supply, so omitting it skips rumor narration entirely rather than
    forcing one on every caller. **Threaded all the way up as of Phase
    248**: `describe_letter_reports()`/`compose_letter_report()` both
    forward their own `board_width` straight into every
    `describe_turn_results()` call they make (one per letter, plus the
    King's own ACTION REPORT), so a real end-to-end letter report
    narrates every leader's own heard rumors once a caller supplies a
    real board width -- see those two composers' own docstrings.
    Reflects **whatever is
    still in `state.rumors` when called**, not just this turn's own new
    ones -- the same single-turn-scope assumption this function already
    made before rumors existed; no multi-turn game loop exists yet for
    it to matter.
    """

    lines: list[str] = []
    for entry in results:
        if entry.error is not None:
            continue
        caster_name = _leader_name(state, entry.leader_id)
        if caster_name is None:
            continue

        if entry.action is ActionCode.HIRE and isinstance(entry.result, HireExecutionResult):
            hireling_name = _leader_name(state, entry.result.request.hero_id)
            if hireling_name is None:
                continue
            line = describe_hire(
                entry.result, character_name=caster_name, hireling_name=hireling_name, king_name=caster_name, rng=rng
            )
        elif entry.action is ActionCode.FIRE and isinstance(entry.result, FireExecutionResult):
            hireling_name = _leader_name(state, entry.result.request.hero_id)
            if hireling_name is None:
                continue
            if entry.result.guild_assassination_queued:
                # Phase 614: _LOAss -- the order-giver's own private
                # notice that this FIRE became a Guild attempt instead.
                line = render_assassination_ordered(caster_name, hireling_name, rng)
            else:
                line = describe_fire(
                    entry.result, character_name=caster_name, hireling_name=hireling_name, king_name=caster_name, rng=rng
                )
        elif entry.action is ActionCode.PRACTICE and isinstance(entry.result, PracticeExecutionResult):
            ability = entry.result.ability
            ability_name = None
            if ability_names is not None and isinstance(ability, Ability):
                ability_name = ability_names.get(ability)
            if ability_name is None:
                continue
            line = describe_practice(entry.result, character_name=caster_name, ability_name=ability_name, rng=rng)
        elif entry.action is ActionCode.CAST and isinstance(entry.result, CastExecutionResult):
            spell = entry.result.request.spell
            if spell not in _AUTO_RESOLVABLE_CAST_TARGET_SPELLS:
                continue
            target_name = _leader_name(state, entry.result.request.target)
            if target_name is None:
                continue
            line = describe_cast(entry.result, caster_name=caster_name, rng=rng, target_name=target_name)
            if line is not None:
                lines.append(line)
            # Phase 612: the Berserk-retaliation duel `describe_cast()`
            # itself can never reach (`applied` stays False on every
            # branch of that outcome) -- a no-op `[]` for every other
            # Cast result.
            lines.extend(
                describe_kill_enemy_berserk_retaliation(
                    entry.result, caster_name=caster_name, target_name=target_name, rng=rng
                )
            )
            continue
        elif entry.action is ActionCode.USE_MI and isinstance(entry.result, UseMIExecutionResult):
            cast_result = entry.result.cast_result
            if cast_result is None:
                continue
            spell = cast_result.request.spell
            if spell not in _AUTO_RESOLVABLE_CAST_TARGET_SPELLS:
                continue
            target_name = _leader_name(state, cast_result.request.target)
            if target_name is None:
                continue
            line = describe_use_mi(entry.result, caster_name=caster_name, rng=rng, target_name=target_name)
        elif entry.action is ActionCode.TRADE and isinstance(entry.result, TradeExecutionResult):
            request = entry.result.request
            if request is None:
                continue
            recipient_name = _leader_name(state, request.target_leader_id)
            if recipient_name is None:
                continue
            item_name = TREASURE_NAME[entry.result.item.treasure] if entry.result.item is not None else None
            line = describe_give(
                entry.result,
                giver_name=caster_name,
                recipient_name=recipient_name,
                item_name=item_name,
                gold_requested=request.obj,
                rng=rng,
            )
        elif entry.action is ActionCode.PURSUE and isinstance(entry.result, PursueExecutionResult):
            request = entry.result.request
            if request is None:
                continue
            target_name = _leader_name(state, request.target_character_id)
            if target_name is None:
                continue
            leader_location = _leader_location(state, entry.leader_id)
            province_name = _province_label(state, leader_location)
            catch_up_line = describe_pursue(
                entry.result, pursuer_name=caster_name, target_name=target_name, province_name=province_name, rng=rng
            )
            if catch_up_line is not None:
                lines.append(catch_up_line)
            # Phase 417: the armyless personal-duel case's own combat --
            # `_fight_army_pursuit_battle()`'s own army-vs-army case has
            # no fire_arrow_shots/melee_swings at all (empty tuples), so
            # this is a genuine no-op for that branch, not a special case.
            province = state.provinces.get(leader_location)
            is_sea = province is not None and province.effective_terrain() is Terrain.SEA
            lines.extend(
                describe_encounter_combat(
                    entry.result,
                    a_leader_id=entry.leader_id,
                    a_name=caster_name,
                    b_name=target_name,
                    rng=rng,
                    is_sea=is_sea,
                )
            )
            continue
        elif entry.action is ActionCode.CHALLENGE and isinstance(entry.result, ChallengeExecutionResult):
            request = entry.result.request
            if request is None:
                continue
            target_name = _leader_name(state, request.target_character_id)
            if target_name is None:
                continue
            province = state.provinces.get(_leader_location(state, entry.leader_id))
            is_sea = province is not None and province.effective_terrain() is Terrain.SEA
            lines.extend(
                describe_challenge(
                    entry.result,
                    challenger_leader_id=entry.leader_id,
                    challenger_name=caster_name,
                    target_name=target_name,
                    rng=rng,
                    is_sea=is_sea,
                )
            )
            continue
        elif entry.action is ActionCode.TRAIL and isinstance(entry.result, TrailExecutionResult):
            request = entry.result.request
            if request is None:
                continue
            target_name = _leader_name(state, request.target_character_id)
            if target_name is None:
                continue
            province_name = _province_label(state, _leader_location(state, entry.leader_id))
            catch_up_line = describe_trail(
                entry.result, trailer_name=caster_name, target_name=target_name, province_name=province_name, rng=rng
            )
            if catch_up_line is not None:
                lines.append(catch_up_line)
            lines.extend(
                describe_trail_intelligence(
                    entry.result, state=state, trailer_name=caster_name, target_name=target_name, rng=rng
                )
            )
            continue
        elif entry.action is ActionCode.SEARCH and isinstance(entry.result, SearchExecutionResult):
            request = entry.result.request
            if request is None:
                continue
            feature = state.features.get(request.feature_id)
            if feature is None:
                continue
            feature_name = _province_label(state, feature.coord)
            province = state.provinces.get(feature.coord)
            is_sea = province is not None and province.effective_terrain() is Terrain.SEA
            lines.extend(
                describe_search(
                    entry.result, state=state, character_name=caster_name, feature_name=feature_name, rng=rng, is_sea=is_sea
                )
            )
            continue
        elif entry.action is ActionCode.ASPY and isinstance(entry.result, SpyReport):
            province_name = _province_label(state, entry.result.province)
            owner_name = (
                _diplomacy_entry(state, entry.result.owner_kingdom_id)
                if entry.result.owner_kingdom_id is not None
                else None
            )
            adjacent_owner_names = [
                _diplomacy_entry(state, kid) for kid in entry.result.adjacent_owners.values() if kid is not None
            ]
            lines.extend(
                describe_aspy(
                    entry.result,
                    spy_name=caster_name,
                    province_name=province_name,
                    owner_name=owner_name,
                    adjacent_owner_names=adjacent_owner_names,
                    rng=rng,
                )
            )
            continue
        elif entry.action is ActionCode.EXPLORE and isinstance(entry.result, ExploreResult):
            for feature in entry.result.discovered_features:
                province_name = _province_label(state, feature.coord)
                lines.extend(describe_feature_discovery(feature, caster_name, province_name, rng))
            continue
        elif entry.action is ActionCode.RECRUIT and isinstance(entry.result, RecruitExecutionResult):
            leader = state.leaders.get(entry.leader_id)
            if leader is None:
                continue
            province = state.provinces.get(leader.location)
            if province is None:
                continue
            lines.extend(
                describe_recruit(entry.result, state, recruiter_name=caster_name, province=province, rng=rng)
            )
            continue
        elif entry.action is ActionCode.LEAVE and isinstance(entry.result, ArmyListExecutionResult):
            leader = state.leaders.get(entry.leader_id)
            if leader is None:
                continue
            province = state.provinces.get(leader.location)
            if province is None:
                continue
            lines.extend(describe_leave(entry.result, state, leader_name=caster_name, province=province, rng=rng))
            continue
        elif entry.action is ActionCode.PICK_UP and isinstance(entry.result, ArmyListExecutionResult):
            leader = state.leaders.get(entry.leader_id)
            if leader is None:
                continue
            province = state.provinces.get(leader.location)
            if province is None:
                continue
            lines.extend(describe_pick_up(entry.result, state, leader_name=caster_name, province=province, rng=rng))
            continue
        elif entry.action is ActionCode.DISBAND and isinstance(entry.result, ArmyListExecutionResult):
            lines.extend(describe_disband(entry.result, state, leader_name=caster_name, rng=rng))
            continue
        elif entry.action is ActionCode.DEFEND and isinstance(entry.result, DefendRequest):
            leader = state.leaders.get(entry.leader_id)
            if leader is None:
                continue
            province = state.provinces.get(leader.location)
            if province is None:
                continue
            lines.append(describe_defend(state, leader_name=caster_name, province=province, rng=rng))
            continue
        elif isinstance(entry.result, DefendReinforcement):
            # Phase 422: matched by result type, not entry.action -- this is
            # one of the sentinel PhaseDispatchResult entries (action=None,
            # segment_index=-1) turn_processor.py appends for events with no
            # real originating PlanPhase this turn, same convention as the
            # "gate-angel-visit"/"forced-rebattle" sentinels.
            lines.append(describe_defend_reinforcement(entry.result, state, defender_name=caster_name, rng=rng))
            continue
        elif isinstance(entry.result, GuildAssassinationOutcome):
            # Phase 614: another sentinel PhaseDispatchResult (leader_id
            # keyed to the *victim*, so caster_name here is already the
            # target's own name, alive-or-dead-aware since Phase 612).
            if entry.result.already_dead:
                lines.append(render_could_not_be_assassinated(caster_name))
            elif entry.result.attempt is not None:
                # attempt is None only if Office.ASSASSIN itself became
                # vacant between the FI interception and phase-5
                # resolution (e.g. the titleholder died in this same
                # turn's battles) -- no sourced text covers that case,
                # so nothing is narrated rather than a dangling _ASeek
                # with no resolution.
                lines.append(render_assassination_attempt(caster_name, rng))
                if entry.result.attempt.succeeded:
                    lines.append(render_assassination_success(caster_name, rng))
                else:
                    lines.append(render_assassination_failed(caster_name, rng))
            continue
        elif entry.action is ActionCode.LMOVE and isinstance(entry.result, MoveExecutionResult):
            if board_width is None:
                continue
            line = describe_move(entry.result, state, character_name=caster_name, board_width=board_width, rng=rng)
            if line is not None:
                lines.append(line)
            continue
        else:
            continue

        if line is not None:
            lines.append(line)

    if board_width is not None:
        heard_leader_ids = {entry.leader_id for entry in results}
        for leader_id in sorted(heard_leader_ids):
            leader = state.leaders.get(leader_id)
            if leader is None or leader.kingdom_id is None:
                continue
            for rumor in state.rumors_heard_by(leader.kingdom_id):
                if rumor.leader_id != leader_id:
                    continue
                lines.append(describe_rumor(rumor, state, leader.name, board_width, rng))

    return lines


# HostAK/TP/SAY.PAS _LTeach -- a single, real, hardcoded template (no
# file), successful Practice tutoring. See module docstring's Phase
# 120 addendum.
PRACTICE_TUTORED_TEMPLATE = "< was tutored/Rinstructed in{ the art of} ^ by [."


def render_practice_tutored(character_name: str, ability_name: str, teacher_name: str, rng: random.Random) -> str:
    """Renders ``_LTeach``'s sentence for successful Practice tutoring.
    ``ability_name`` is ``PROSE.TXT``'s own ``^`` marker.
    """

    values = {"<": character_name, "^": ability_name, "[": teacher_name}
    return render(PRACTICE_TUTORED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LAlrMax -- a single, real, hardcoded template (no
# file), immediately follows _LTeach in RUMORS.PAS's own CONST block.
# See module docstring's Phase 120 addendum.
PRACTICE_ALREADY_MAXED_TEMPLATE = (
    "< practiced ^ even though < had already reached the maximum skill level."
)


def render_practice_already_maxed(character_name: str, ability_name: str, rng: random.Random) -> str:
    """Renders ``_LAlrMax``'s sentence for Practice at an already-maxed
    skill level (``turn/practice_execution.py``'s own already-modeled
    rule).
    """

    values = {"<": character_name, "^": ability_name}
    return render(PRACTICE_ALREADY_MAXED_TEMPLATE, values, rng=rng)


# HostAK/TP/PROSE/PRACVAIN.X -- a normal failed Practice roll (Phase
# 601). `SAY.PAS:687 _LStudV: FD('pracvain',S_Priv,1)`. Closes the exact
# gap `describe_practice()`'s own docstring already named: "a normal
# failed roll... has no sourced narrative and renders nothing" -- now it
# does. ``^`` is the same ability-name marker ``render_practice_
# tutored()``/``render_practice_already_maxed()`` already use.
_PRACVAIN_TEMPLATES: list[str] = [
    "< {really }tried hard to improve > ^, but < practiced in vain.",
    "< practiced > ^ {diligently }for many_weeks/Rmonths, but could "
    "make no {significant }headway/Rprogress.",
    "< practiced > ^ well{, and even consulted "
    "a_palm_reader/Ran_astrologer,} but could not improve > "
    "{skill in }^.",
    "< worked {hard }on > ^ but was thwarted/Rfrustrated in > "
    "{self-improvement }efforts.",
]


def render_practice_vain(character_name: str, ability_name: str, rng: random.Random) -> str:
    """Renders PRACVAIN.X's sentence for a normal failed Practice roll
    (Phase 601) -- no skill rise, no aptitude rise, not an already-maxed
    skill.
    """

    variant = pick_variant(_PRACVAIN_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s", "^": ability_name}
    return render(variant, values, rng=rng)


def describe_practice(
    result: PracticeExecutionResult,
    *,
    character_name: str,
    ability_name: str,
    teacher_name: str | None = None,
    rng: random.Random,
) -> str | None:
    """Assembles the one-sentence Practice narrative from an already-computed
    ``PracticeExecutionResult`` (``turn/practice_execution.py
    execute_practice()``/``execute_practice_group()``, Phase 44/46) --
    the same ``describe_give()``-style composer (Phase 142).

    Three of this project's Practice renderers are reachable here, each
    needing information ``PracticeExecutionResult`` alone doesn't
    always carry, matching ``describe_battle()``'s own caller-supplies-
    names convention:

    - ``render_practice_already_maxed`` (``_LAlrMax``) fires when the
      attempt started at ``MAX_SKILL_LEVEL`` (9, ``CTBOTH.PAS``'s own
      ``skillrange`` ceiling): ``turn/practice_execution.py
      _resolve_practice_attempt()`` short-circuits to ``skill_rose=False``
      with ``new_skill`` unchanged in that case,
      the *only* way ``new_skill == MAX_SKILL_LEVEL`` can coexist with
      ``skill_rose is False`` (a failed roll from any lower level
      leaves ``new_skill`` at that lower level, never at 9).
    - ``render_practice_tutored`` (``_LTeach``) fires when the skill
      genuinely rose (``skill_rose``) *and* the caller supplies a
      ``teacher_name`` -- the higher-skilled co-practicer rulebook
      [3.13]'s own group-practice rule requires, which
      ``PracticeExecutionResult`` has no field for at all (it doesn't
      even record whether this was a solo or group attempt). Leave
      ``teacher_name`` unset for a solo rise: no sourced narrative
      template exists for solo success at all, so nothing is rendered.
    - **Phase 601**: ``render_practice_vain`` (``_LStudV``) fires for a
      genuine total failure -- not already-maxed, ``skill_rose`` False,
      and (unlike the prior two cases above, which already exclude it)
      also ``aptitude_rose`` False and ``not_implemented_for_ability``
      False, since an aptitude-only rise did achieve *something* and an
      implementation gap is an engineering limitation, not an in-game
      "practiced in vain" outcome -- neither should be narrated as one.
    - Every remaining case (an aptitude-only rise, a solo skill rise
      with no ``teacher_name``, ``not_implemented_for_ability``) still
      has no sourced narrative and renders nothing.
    """

    if result.new_skill == MAX_SKILL_LEVEL and not result.skill_rose:
        return render_practice_already_maxed(character_name, ability_name, rng)
    if result.skill_rose and teacher_name is not None:
        return render_practice_tutored(character_name, ability_name, teacher_name, rng)
    if not result.skill_rose and not result.aptitude_rose and not result.not_implemented_for_ability:
        return render_practice_vain(character_name, ability_name, rng)
    return None


# HostAK/TP/PROSE/DISCOV.X -- Sage's device-discovery success (rulebook
# [4.3.1], SAY.PAS's own `_LDisc` report code, Phase 266). Real, extracted
# file content: "1 1\nin > sagely researches, < discovered  fabulous
# invention called the !" -- markers `>` (possessive), `<` (character
# name), `!` (discovery name), matching this project's established
# marker conventions elsewhere (e.g. render_commander_died_demoralized).
# The double space before "fabulous" is the same lost-marker extraction
# artifact this project has already resolved elsewhere: "discovered"
# then a lone consonant-initial noun phrase needing an article is
# exactly what `^A` (Phase 118's own auto a/an marker, e.g. "^A
# dungeon") produces, so `^A` is restored there rather than left as a
# raw double space or a silently invented literal "a". Standalone, not
# yet wired into describe_practice()'s single-line-per-entry dispatch:
# the device-discovery roll is independent of ("on top of, not instead
# of") the ordinary skill-rise roll describe_practice() already
# prioritizes between, so a call with both outcomes true would need an
# unsourced priority decision between two genuinely-narratable sourced
# templates -- left to a real composer-wiring phase rather than guessed
# at here, the same "renderer exists, full wiring later" precedent
# already used for render_wandering_encounter (Phase 106) and others
# before their own eventual composer wiring.
_DISCOVERY_TEMPLATE = "in > sagely researches, < discovered ^A fabulous invention called the !"


def render_sage_discovery(character_name: str, discovery: Discovery, rng: random.Random) -> str:
    """Renders DISCOV.X's own device-discovery success line for ``discovery``."""

    values = {">": f"{character_name}'s", "<": character_name, "!": DISCOVERY_NAME[discovery]}
    return render(_DISCOVERY_TEMPLATE, values, rng=rng)


# SAY.PAS `_LNoDisc` -- Sage's device-discovery failure line (the same
# report code slot DISCOV.X's own success line occupies, `_LDisc`, sits
# right next to). See render_sage_discovery()'s own docstring for why
# this isn't yet wired into describe_practice() either.
_NO_DISCOVERY_TEMPLATE = "< discovered/Rinvented nothing {valuable/Rworthy_of_note }in > sagely researches/Rexperiments."


def render_sage_no_discovery(character_name: str, rng: random.Random) -> str:
    """Renders SAY.PAS's own ``_LNoDisc`` line for a Sage practice attempt
    that rolled no device discovery this phase."""

    values = {"<": character_name, ">": f"{character_name}'s"}
    return render(_NO_DISCOVERY_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _ADishK -- a real entry made of two separate
# Say(...) calls (no file): the Supreme Commander died, demoralizing
# the losing side (rulebook [7.1], turn/duel.py apply_duel_
# demoralization()). See module docstring's Phase 121 addendum.
_COMMANDER_DIED_TEMPLATES = (
    "The forces commanded by [3 were disheartened by ] death/Rdemise, ",
    "but/Ryet still they pressed/Rmoved forward/Rahead with some hope of victory.",
)


def render_commander_died_demoralized(commander_name: str, rng: random.Random) -> str:
    """Renders ``_ADishK``'s two-sentence entry: the Supreme Commander
    died, demoralizing their own side. Concatenated with no separator
    (see module docstring).
    """

    values = {"[3": commander_name, "]": f"{commander_name}'s"}
    first = render(_COMMANDER_DIED_TEMPLATES[0], values, rng=rng)
    second = render(_COMMANDER_DIED_TEMPLATES[1], values, rng=rng)
    return first + second


# HostAK/TP/SAY.PAS _ADishF -- a real entry made of two separate
# Say(...) calls (no file): the Supreme Commander fled/was cowardly,
# demoralizing the losing side (rulebook [7.1], the same mechanic
# _ADishK narrates). See module docstring's Phase 121 addendum.
_COMMANDER_FLED_TEMPLATES = (
    "The forces commanded by <3 were disappointed/Rdismayed by > cowardice/Rfaint-heartedness.",
    "They {grimly/Rsteadfastly }marched on, though with lessened/Rshaken confidence.",
)


def render_commander_fled_demoralized(commander_name: str, rng: random.Random) -> str:
    """Renders ``_ADishF``'s two-sentence entry: the Supreme Commander
    fled/was cowardly, demoralizing their own side. Concatenated with
    no separator (see module docstring). This project has no source
    for what decides between this narration and ``render_commander_
    died_demoralized()`` -- the caller decides.
    """

    values = {"<3": commander_name, ">": f"{commander_name}'s"}
    first = render(_COMMANDER_FLED_TEMPLATES[0], values, rng=rng)
    second = render(_COMMANDER_FLED_TEMPLATES[1], values, rng=rng)
    return first + second


# HostAK/TP/PROSE/FLEEFAIL.X -- a failed Flee maneuver. See module
# docstring's Phase 105 addendum.
_FLEEFAIL_TEMPLATES: list[str] = [
    "< attempted/Rtried to flee from the fight/Rcombat, but [1 {cleverly }cornered <2.",
    "< turned {around so as }to flee from [, but found/Rsaw that > "
    "path_of_retreat/Rretreat_route had been magically blocked by ^A "
    "wall/Rcurtain of fire/Rshimmering_force.",
    "< ran/Sswam_away from the melee/Rcombat, but "
    "slipped_and_fell/Sscraped_against_a_submerged_rock.< injured > "
    "leg/Rankle and could not escape/Rget_away!",
    "desiring_only/RHoping to escape from > vicious/Rterrible "
    "opponent/Rfoe, < ran/Sswam like the_wind/Sa_crazed_shark.But < was "
    "too_tired/Rexhausted and{, even with great effort,} could not gain "
    "{any }ground/Sdistance on [.",
]


def render_flee_failure(
    fleeing_character: str, opponent_name: str, rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders FLEEFAIL.X's sentence for a failed Flee maneuver (an
    encounter's ``Maneuver.FLEE``). ``is_sea`` (Phase 74) resolves the
    "/S" marker 2 of the 4 variants carry.
    """

    variant = pick_variant(_FLEEFAIL_TEMPLATES, rng)
    values = {
        "<": fleeing_character,
        "<2": fleeing_character,
        "[": opponent_name,
        "[1": opponent_name,
        ">": f"{fleeing_character}'s",
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/SNEAKUP.X -- a failed Steal maneuver, caught mid-theft.
# Every template ends mid-sentence with "at", completed by one of these
# three confirmed range clauses (see module docstring's Phase 105
# addendum for why the choice among them isn't made here).
SNEAKUP_RANGE_MELEE = " melee range."
SNEAKUP_RANGE_BOW = " bow range."
SNEAKUP_RANGE_SPELL = " spell range."

_SNEAKUP_TEMPLATES: list[str] = [
    "< tried to sneak by [, but was seen/Rdetected at",
    "despite > {great/Rremarkable }caution/Rstealth, < was "
    "detected/Rperceived by [ {before anything/Rany_treasure could be "
    "stolen/Rtaken }and engaged at",
    "< stole quietly/Rsilently up to the treasure of [, but "
    "unfortunately < was noticed/Rseen.< had to encounter [ at",
    "< hoped/Rtried to steal/Rtake the {great/Rvaluable }treasures of [ "
    "{without being noticed/Rseen, }but [1 spotted/Rnoticed < at",
]


def render_sneak_detected(
    character_name: str, opponent_name: str, range_suffix: str, rng: random.Random
) -> str:
    """Renders SNEAKUP.X's sentence for a failed Steal maneuver, caught
    mid-theft. ``range_suffix`` completes the sentence -- pass one of
    ``SNEAKUP_RANGE_MELEE``/``SNEAKUP_RANGE_BOW``/``SNEAKUP_RANGE_SPELL``
    (the three confirmed clauses `SAY.PAS`'s own dispatch selects
    between; this project has no source for which situational fact picks
    one over the others, the same caller-supplied-fact pattern as
    ``is_sea``).
    """

    variant = pick_variant(_SNEAKUP_TEMPLATES, rng)
    values = {
        "<": character_name,
        "[": opponent_name,
        "[1": opponent_name,
        ">": f"{character_name}'s",
    }
    return render(variant, values, rng=rng) + range_suffix


_STEAL_CAPTURE_RANGE_SUFFIX: dict[CombatRange, str] = {
    CombatRange.MELEE_RANGE: SNEAKUP_RANGE_MELEE,
    CombatRange.BOW_RANGE: SNEAKUP_RANGE_BOW,
    CombatRange.SPELL_RANGE: SNEAKUP_RANGE_SPELL,
}


def describe_steal(
    result: ChallengeExecutionResult | PursueExecutionResult,
    *,
    thief_name: str,
    victim_name: str,
    rng: random.Random,
) -> str | None:
    """Assembles the Steal sub-event narrative from an already-computed
    ``ChallengeExecutionResult`` (``turn/challenge_execution.py
    execute_challenge()``, Phase 305/306) -- the same ``describe_hire()``
    -style composer, reused by Pursue's own ``PursueExecutionResult``
    (which shares the same ``steal_outcome``/``steal_capture_range``
    field names -- see that module's own docstring) via a plain
    attribute read, not an isinstance check.

    Wires two real, previously-unconsumed renderers (both already
    sourced, tested, and dispatch-ready before this phase, per their own
    module docstring addenda -- Phase 105's ``render_sneak_detected`` and
    Phase 119's ``render_steal_caught_and_ransomed``):

    - ``"combat"`` -> ``render_sneak_detected()`` (``SNEAKUP.X``): caught
      mid-theft, engaged at whichever range ``_resolve_steal_tactic()``
      rolled. Whether real combat actually follows in the same report is
      a separate question this function doesn't answer -- see ``turn/
      challenge_execution.py``'s own Phase 306 addendum for how the
      mechanic itself now hands off to the plan's next tactic instead of
      resolving atomically.
    - ``"ransom"`` -> ``render_steal_caught_and_ransomed()`` (``_LRans``):
      a King caught robbing another King, forced to pay half his own
      treasury. ``victim_name`` is the *catcher* here (the King who was
      almost robbed), ``thief_name`` the one who paid -- matching that
      renderer's own ``catcher_name``/``thief_name`` parameter order.
    - ``"success"``/``"evaded"``/``"executed"``/``"unresolved"``/``None``
      all have no sourced narrative template of their own (a clean gold
      or item theft was never given prose in any available source, and
      no sourced text describes a Hero's own execution or a genuinely
      unresolved capture) -- returns ``None``, the same "no source, no
      guess" convention every other ``describe_*`` composer in this
      module already follows for its own undocumented failure reasons.
    """

    if result.steal_outcome == "ransom":
        return render_steal_caught_and_ransomed(victim_name, thief_name, rng)
    if result.steal_outcome == "combat" and result.steal_capture_range is not None:
        range_suffix = _STEAL_CAPTURE_RANGE_SUFFIX[result.steal_capture_range]
        return render_sneak_detected(thief_name, victim_name, range_suffix, rng)
    return None


# HostAK/TP/PROSE/RWENC.X -- a wandering encounter's opening sentence.
# See module docstring's Phase 106 addendum.
_RWENC_TEMPLATES: list[str] = [
    "< was crossing_an_open_field/Sswimming_in_a_lagoon when [1 spotted <2 from a distance.",
    "< was {unexpectedly }approached_by/Rfaced_with [.",
    "[1 {suddenly/Runexpectedly }came_at/Rrushed_at <2 from_out_of_nowhere/Rlike_a_bolt_from_the_blue.",
    "< encountered/Rwas_confronted_by [.",
]


def render_wandering_encounter(
    character_name: str, other_name: str, rng: random.Random, *, is_sea: bool = False
) -> str:
    """Renders RWENC.X's opening sentence for a wandering encounter while
    traveling (distinct from Search's own ``models/intro.py Intro``,
    Phase 99, which is about discovering a geographic ``Feature``, not a
    chance meeting on the road). ``is_sea`` (Phase 74) resolves the "/S"
    marker the first variant carries.
    """

    variant = pick_variant(_RWENC_TEMPLATES, rng)
    values = {
        "<": character_name,
        "<2": character_name,
        "[": other_name,
        "[1": other_name,
    }
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/PROSE/ENCO.X -- the simplest possible encounter opening. See
# module docstring's Phase 107 addendum.
_ENCO_TEMPLATES: list[str] = [
    "< encountered [.",
]


def render_generic_encounter(character_name: str, other_name: str, rng: random.Random) -> str:
    """Renders ENCO.X's sentence -- the simplest encounter opening, a
    single template with no real variation to pick from.
    """

    variant = pick_variant(_ENCO_TEMPLATES, rng)
    values = {"<": character_name, "[": other_name}
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/SAFPAT.X -- caught, then released. See module
# docstring's Phase 107 addendum.
_SAFPAT_TEMPLATES: list[str] = [
    "but when < was taken to the judge/Rlocal_sheriff, < "
    "showed_him/Rheld_forth the official_seal/Rinsignia of ^K, and was "
    "let_go/Rmerely_run_out_of_town.",
    "but he was easily/Rjust dazzled/Rawed by <'s "
    "{fantastic/Rwonderful }tales of > heroism/Radventures.he "
    "{respectfully/Radmiringly }bowed_before/Rsaluted <2 and {then "
    "}marched_away/Rdeparted.",
    "but < wasn't_listed_as_^A/Rwas_obviously_no {wanted/Rrenegade "
    "}outlaw/Rspy, and_that_got_<2/Rso_<_got off_the_hook/Rout_of_trouble.",
]


def render_patrol_release(character_name: str, king_name: str, rng: random.Random) -> str:
    """Renders SAFPAT.X's sentence for getting caught but then released
    (a convincing official seal, an impressed judge, not actually being
    on a wanted list). ``king_name`` is ``PROSE.TXT``'s own ``^K``
    marker ("King name and title", e.g. "King Harold the Bold").
    """

    variant = pick_variant(_SAFPAT_TEMPLATES, rng)
    values = {
        "<": character_name,
        "<2": character_name,
        ">": f"{character_name}'s",
        "^K": king_name,
    }
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/PATENC.X -- a more dangerous patrol/bounty-hunter
# encounter. See module docstring's Phase 107 addendum.
_PATENC_TEMPLATES: list[str] = [
    "< was ambushed/Rchased, tied_up/Rpinned_down and "
    "severely_beaten/Rbloodied_up by wild-eyed_soldiers/Rangry_vigilantes."
    "< {finally }escaped/Rbroke_free.a King's/RRoyal Ranger/RMarshal "
    "tracked_<2_down/Rcaught_up_with_<2.",
    "< was stopped/Rspotted by a {local }patrol/Rband_of_militia.Their "
    "commanding officer/Rcaptain suspiciously/Rthreateningly challenged <2.",
    "< was challenged/Rconfronted by a Royal_bounty_hunter/Rlocal_sheriff "
    "who apparently/Revidently thought/Rbelieved < was a spy/Rwanted_criminal.",
    "< was badgered/Raccosted by ^A {drunken/Rboorish }officer/Rrogue who "
    "insulted/Rridiculed the respected/Rproud name_of_</RKingdom_of_^K."
    "< killed/Rslew him in a duel, but the rogue's older_brother/Rbest_friend "
    "was a marshal/Rcolonel, and he came after <2!",
]


def render_patrol_encounter(character_name: str, king_name: str, rng: random.Random) -> str:
    """Renders PATENC.X's sentence for a more dangerous patrol/bounty
    -hunter encounter. ``king_name`` is ``PROSE.TXT``'s own ``^K`` marker
    (see ``render_patrol_release()``).
    """

    variant = pick_variant(_PATENC_TEMPLATES, rng)
    values = {
        "<": character_name,
        "<2": character_name,
        "^K": king_name,
    }
    return render(variant, values, rng=rng)


# HostAK/TP/SAY.PAS _LPIce -- a single, real, hardcoded template (no
# file). See module docstring's Phase 123 addendum.
ICE_SUSPEND_FAILED_TO_HOLD_TEMPLATE = (
    "but the shell/Rice was not strong/Rthick enough to hold/Rstop [, "
    "and [1 began to break_out/Rcrack_through."
)


def render_ice_suspend_failed_to_hold(target_name: str, rng: random.Random) -> str:
    """Renders ``_LPIce``'s sentence: the Ice-Suspend shell fails to
    fully hold the target, who begins breaking free immediately.
    """

    values = {"[": target_name, "[1": target_name}
    return render(ICE_SUSPEND_FAILED_TO_HOLD_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LBIce -- a single, real, hardcoded template (no
# file). See module docstring's Phase 123 addendum.
ICE_BREAK_OUT_ATTEMPT_TEMPLATE = (
    "< struggled/Rattempted to break out of > {frosty }shell/Rprison "
    "of {cold/Rfrigid }ice."
)


def render_ice_break_out_attempt(character_name: str, rng: random.Random) -> str:
    """Renders ``_LBIce``'s sentence: the target's own attempt to
    break free of the Ice-Suspend shell (not yet resolved).
    """

    values = {"<": character_name, ">": f"{character_name}'s"}
    return render(ICE_BREAK_OUT_ATTEMPT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFIce -- a single, real, hardcoded template (no
# file). See module docstring's Phase 123 addendum.
ICE_BREAK_OUT_SUCCESS_TEMPLATE = (
    "with a mighty heave/Reffort, < broke out of > {frosty }shell/Rprison "
    "of {cold/Rfrigid }ice."
)


def render_ice_break_out_success(character_name: str, rng: random.Random) -> str:
    """Renders ``_LFIce``'s sentence: the target successfully breaks
    free of the Ice-Suspend shell.
    """

    values = {"<": character_name, ">": f"{character_name}'s"}
    return render(ICE_BREAK_OUT_SUCCESS_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LIceCr -- a single, real, hardcoded template (no
# file). See module docstring's Phase 123 addendum.
ICE_FALL_DAMAGE_TEMPLATE = "[1 dropped/Rcrashed, suffering/Rtaking # damage points."


def render_ice_fall_damage(target_name: str, damage_points: int, rng: random.Random) -> str:
    """Renders ``_LIceCr``'s sentence: fall damage after the
    Ice-Suspend shell releases/shatters. ``damage_points`` is
    ``PROSE.TXT``'s own ``#`` marker, the same convention
    ``render_attack_hit()`` (Phase 112) already established.
    """

    values = {"[1": target_name, "#": str(damage_points)}
    return render(ICE_FALL_DAMAGE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LIceGh -- a single, real, hardcoded template (no
# file). See module docstring's Phase 123 addendum.
ICE_GHOST_IMMUNE_TEMPLATE = "but ['s translucent form easily glided through the ice."


def render_ice_ghost_immune(target_name: str, rng: random.Random) -> str:
    """Renders ``_LIceGh``'s sentence: an incorporeal/ghost-type
    target is immune to the Ice-Suspend shell entirely.
    """

    values = {"[": target_name}
    return render(ICE_GHOST_IMMUNE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LShIce -- a single, real, hardcoded template (no
# file). See module docstring's Phase 123 addendum.
ICE_IMMOBILIZED_TEMPLATE = (
    "[1 was immobilized_by/Rlocked_in the {frosty }shell/Rprison of "
    "{cold/Rfrigid }ice."
)


def render_ice_immobilized(target_name: str, rng: random.Random) -> str:
    """Renders ``_LShIce``'s sentence: the target's immobilized state
    under the Ice-Suspend shell, distinct from the cast announcement
    itself (``SPELL_CAST_ANNOUNCEMENT[Spell.ICE_SUSPEND]``, Phase 122).
    """

    values = {"[1": target_name}
    return render(ICE_IMMOBILIZED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LWMelt -- a single, real, hardcoded template (no
# file). See module docstring's Phase 123 addendum.
ICE_WAIT_FOR_MELT_TEMPLATE = "< stood away from [ and waited for the ice to melt."


def render_ice_wait_for_melt(character_name: str, target_name: str, rng: random.Random) -> str:
    """Renders ``_LWMelt``'s sentence: the opponent's own tactical
    choice not to attack a frozen target and instead wait for the ice
    to melt.
    """

    values = {"<": character_name, "[": target_name}
    return render(ICE_WAIT_FOR_MELT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LSFroz -- a single, real, hardcoded template (no
# file), using ``report/prose.py``'s ``^L`` list insertion (Phase 118).
# See module docstring's Phase 123 addendum.
ICE_STEAL_BLOCKED_TEMPLATE = (
    "< could not take the ^L\\ because what [1 carried was frozen in with [."
)


def render_ice_steal_blocked(
    character_name: str, target_name: str, item_names: list[str], rng: random.Random
) -> str:
    """Renders ``_LSFroz``'s sentence: a blocked Steal/Take-item
    attempt against a frozen target. ``item_names`` is ``PROSE.TXT``'s
    own ``\\`` marker (Magic Item), joined via ``^L`` list insertion,
    the same shape ``render_take_items()`` (Phase 118) already
    established.
    """

    values = {"<": character_name, "[1": target_name, "[": target_name}
    return render(ICE_STEAL_BLOCKED_TEMPLATE, values, rng=rng, lists={"\\": item_names})


# HostAK/TP/SAY.PAS _LFinance -- a single, real, hardcoded template (no
# file). See module docstring's Phase 124 addendum.
FINANCE_REPORT_OPENING_TEMPLATE = "here is the financial report for <'s kingdom: "


def render_finance_report_opening(character_name: str, rng: random.Random) -> str:
    """Renders ``_LFinance``'s sentence: the Financial Report section's
    opening clause.
    """

    values = {"<": character_name}
    return render(FINANCE_REPORT_OPENING_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LRev -- a single, real, hardcoded template (no
# file). See module docstring's Phase 124 addendum.
FINANCE_REVENUE_TEMPLATE = "this turn, the Kingdom collected # gold in revenue."


def render_finance_revenue(gold_amount: int, rng: random.Random) -> str:
    """Renders ``_LRev``'s sentence: this turn's revenue collected."""

    values = {"#": str(gold_amount)}
    return render(FINANCE_REVENUE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LLCosts -- a single, real, hardcoded template (no
# file). See module docstring's Phase 124 addendum.
FINANCE_LEADER_COSTS_TEMPLATE = "# gold was expended to finance our leaders."


def render_finance_leader_costs(gold_amount: int, rng: random.Random) -> str:
    """Renders ``_LLCosts``'s sentence: this turn's leader upkeep cost."""

    values = {"#": str(gold_amount)}
    return render(FINANCE_LEADER_COSTS_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _AUnpaid -- a single, real, hardcoded template (no
# file). See module docstring's Phase 124 addendum.
FINANCE_UNPAID_ARMIES_TEMPLATE = (
    "unfortunately, #% of your Majesty's armies had to go without pay."
)


def render_finance_unpaid_armies(percent: int, rng: random.Random) -> str:
    """Renders ``_AUnpaid``'s sentence: the percentage of armies that
    went unpaid this turn. This project has no source for when this
    sentence is included versus omitted -- the caller decides whether
    to call it at all.
    """

    values = {"#": str(percent)}
    return render(FINANCE_UNPAID_ARMIES_TEMPLATE, values, rng=rng)


# HostAK/TP/PROSE/LDESERT.X -- a Hero quitting their King's service over
# unpaid wages (Phase 599). `SAY.PAS:791 _LDesert: FD('ldesert',S_PCom,
# 0)`. Unlike Phase 598's own model gap, ``turn/expenses.py
# apply_turn_maintenance()``'s own ``MaintenanceResult.deserted_
# leader_ids`` (Phase 527, ``AKGEN_reverse_engineering_report (3).md``
# SS28.1's real compiled desertion roll) is an exact match for this
# template's own real content -- all four choices name "the lack of
# pay"/"no pay"/"back pay" as the reason, the identical mechanic
# ``deserted_leader_ids`` already computes. ``describe_desertions()``
# below wires it in directly, the same shape ``describe_recruit()``
# already established for a per-unit result list.
_LDESERT_TEMPLATES: list[str] = [
    "< quit/Rretired_from the service of [, grumbling/Rcarping about "
    "the lack of pay.",
    "< {grew }tired of working/Rfighting for [ with/Rfor no pay and "
    "handed_in/Rsubmitted > resignation.",
    "< left [ to find employment/Radventure elsewhere, hoping to "
    "find ^A more_consistent/Rbetter source of income.",
    "< could not {be persuaded to }stay {in the service of [ "
    "}without {getting > back }pay, {and }so < left [ to answer "
    "the {high }call of adventure.",
]


def render_hero_deserted(character_name: str, king_name: str, rng: random.Random) -> str:
    """Renders LDESERT.X's sentence for a Hero deserting their King's
    service over unpaid wages (Phase 599).
    """

    variant = pick_variant(_LDESERT_TEMPLATES, rng)
    values = {"<": character_name, "[": king_name, ">": f"{character_name}'s"}
    return render(variant, values, rng=rng)


def describe_desertions(result: MaintenanceResult, state: GameState, *, king_name: str, rng: random.Random) -> list[str]:
    """Assembles one LDESERT.X sentence per Hero who deserted this turn
    (Phase 599) -- ``result.deserted_leader_ids``, from ``turn/
    expenses.py apply_turn_maintenance()``. A deserted leader stays in
    ``state.leaders`` (only ``kingdom_id`` is cleared), so ``_leader_
    name()`` still resolves their name at narration time.
    """

    lines: list[str] = []
    for leader_id in result.deserted_leader_ids:
        character_name = _leader_name(state, leader_id)
        if character_name is None:
            continue
        lines.append(render_hero_deserted(character_name, king_name, rng))
    return lines


# HostAK/TP/SAY.PAS _LACosts -- a single, real, hardcoded template (no
# file). See module docstring's Phase 124 addendum.
FINANCE_ARMY_COSTS_TEMPLATE = "# gold was expended to maintain our armies."


def render_finance_army_costs(gold_amount: int, rng: random.Random) -> str:
    """Renders ``_LACosts``'s sentence: this turn's army upkeep cost."""

    values = {"#": str(gold_amount)}
    return render(FINANCE_ARMY_COSTS_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LTreas -- a single, real, hardcoded template (no
# file). See module docstring's Phase 124 addendum.
FINANCE_TREASURY_TEMPLATE = "< was left with # gold in the treasury."


def render_finance_treasury(character_name: str, gold_amount: int, rng: random.Random) -> str:
    """Renders ``_LTreas``'s sentence: the closing treasury balance,
    ties directly to ``GameState.KingdomState.treasury``'s own
    post-turn value (Phase 9).
    """

    values = {"<": character_name, "#": str(gold_amount)}
    return render(FINANCE_TREASURY_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LOAss -- a single, real, hardcoded template (no
# file). See module docstring's Phase 125 addendum.
ASSASSINATION_ORDERED_TEMPLATE = "< ordered the assassination of [."


def render_assassination_ordered(character_name: str, target_name: str, rng: random.Random) -> str:
    """Renders ``_LOAss``'s sentence: the order/directive to assassinate
    a target.
    """

    values = {"<": character_name, "[": target_name}
    return render(ASSASSINATION_ORDERED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _ASeek -- a single, real, hardcoded template (no
# file). See module docstring's Phase 125 addendum.
ASSASSINATION_ATTEMPT_TEMPLATE = (
    "While [1 was out_for_a_stroll/Rin_meditation, suddenly an{ unknown} "
    "assassin launched himself{ from out of the dark} at [!"
)


def render_assassination_attempt(target_name: str, rng: random.Random) -> str:
    """Renders ``_ASeek``'s sentence: the assassination attempt begins."""

    values = {"[1": target_name, "[": target_name}
    return render(ASSASSINATION_ATTEMPT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _AKill -- a single, real, hardcoded template (no
# file). See module docstring's Phase 125 addendum.
ASSASSINATION_SUCCESS_TEMPLATE = (
    "[1 was wounded/Rstabbed by a_poisoned/Rhis_poisonous dagger!"
    "Cursed be the Assassin's Guild and whoever heads it!"
)


def render_assassination_success(target_name: str, rng: random.Random) -> str:
    """Renders ``_AKill``'s sentence: the assassination attempt succeeds."""

    values = {"[1": target_name}
    return render(ASSASSINATION_SUCCESS_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _AFail -- a real, two-``Say()`` entry (no file).
# See module docstring's Phase 125 addendum.
_ASSASSINATION_FAILED_TEMPLATES = (
    "Fortunately, [1 survived the attempt and the assassin (apparently, "
    "a member of the Assassin's Guild) was killed.",
    "Of_course/RWithout_delay, the guard in/Rthroughout ['s kingdom was "
    "{immediately }doubled.",
)


def render_assassination_failed(target_name: str, rng: random.Random) -> str:
    """Renders ``_AFail``'s two sentences: the assassination attempt
    fails, the assassin is killed, and the target's guard is doubled.
    Concatenates both rendered sentences with no separator, the same
    shape established throughout this module (Phase 107, 116, 119, 121).
    """

    values = {"[1": target_name, "[": target_name}
    first = render(_ASSASSINATION_FAILED_TEMPLATES[0], values, rng=rng)
    second = render(_ASSASSINATION_FAILED_TEMPLATES[1], values, rng=rng)
    return first + second


# HostAK/TP/PROSE/ILLEG.X2, record 91 (Phase 614) -- see module
# docstring's Phase 614 addendum above. A single, real, hardcoded
# sentence, no `/R`/`{}` choice markers, so no `rng` parameter -- the
# same "nothing to vary" shape `render_magic_feature_discovery()`
# already established.
COULD_NOT_BE_ASSASSINATED_TEMPLATE = "[1 could not be assassinated because [1 was dead and buried."


def render_could_not_be_assassinated(target_name: str) -> str:
    """Renders ``ILLEG.X2`` record 91: the Grandfather of Assassins'
    queued target was already dead by phase-5 resolution time (Phase
    614) -- see ``turn/assassin_guild.py GuildAssassinationOutcome``'s
    own ``already_dead`` field.
    """

    values = {"[1": target_name}
    return render(COULD_NOT_BE_ASSASSINATED_TEMPLATE, values)


# HostAK/TP/SAY.PAS _BFun -- a single, real, hardcoded template (no
# file). See module docstring's Phase 126 addendum.
SKELETAL_ARMY_FERVOR_TEMPLATE = (
    "The Skeletal Armies led by < marched into battle with a fanatical fervor."
)


def render_skeletal_army_fervor(commander_name: str, rng: random.Random) -> str:
    """Renders ``_BFun``'s sentence: Skeletal Armies march into battle
    with fanatical fervor -- ties to ``Spell.SKELETAL_ARMY`` (Phase 122).
    """

    values = {"<": commander_name}
    return render(SKELETAL_ARMY_FERVOR_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _BSpeech -- a real, two-``Say()`` entry (no file).
# See module docstring's Phase 126 addendum.
_ORATORY_SPEECH_TEMPLATES = (
    "using/Rcalling_upon > magical/Rarcane powers/RSpell of Oratory, ",
    "< gave/Rstarted_with ^A rousing/Rinspiring speech/Rharangue to "
    "> troops/Rarmy, raising/Rwhich_bolstered their courage/Rmorale.",
)


def render_oratory_speech(commander_name: str, rng: random.Random) -> str:
    """Renders ``_BSpeech``'s two sentences: a leader rouses their
    troops via the Oratory spell (``Spell.ORATORY``, Phase 122).
    Concatenates both rendered sentences with no separator, the same
    shape established throughout this module (Phase 107, 116, 119,
    121, 125).
    """

    values = {"<": commander_name, ">": f"{commander_name}'s"}
    first = render(_ORATORY_SPEECH_TEMPLATES[0], values, rng=rng)
    second = render(_ORATORY_SPEECH_TEMPLATES[1], values, rng=rng)
    return first + second


# HostAK/TP/SAY.PAS _BHome -- a single, real, hardcoded template (no
# file). See module docstring's Phase 126 addendum.
HOMELAND_DEFENSE_MORALE_TEMPLATE = (
    "<'s troops/Rsoldiers were_prepared/Rswore to fight/Rstruggle "
    "desperately/Rlike_tigers for their homeland/Rfatherland."
)


def render_homeland_defense_morale(commander_name: str, rng: random.Random) -> str:
    """Renders ``_BHome``'s sentence: troops defending their home
    province fight with elevated morale.
    """

    values = {"<": commander_name}
    return render(HOMELAND_DEFENSE_MORALE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _BRWeap -- a single, real, hardcoded template (no
# file). See module docstring's Phase 126 addendum.
WEAPON_RALLY_TEMPLATE = (
    "< waved/Rheld_aloft > \\ and the/R> ^R "
    "cheered_wildly/Rwere_virtually_hypnotized{ with/Rin admiration/Rit's_enchanted_glow}!"
)


def render_weapon_rally(commander_name: str, weapon_name: str, race_name: str, rng: random.Random) -> str:
    """Renders ``_BRWeap``'s sentence: a leader brandishes a magic
    item to rally their troops. ``race_name`` is ``PROSE.TXT``'s own
    ``^R`` marker (``models/race.py RACE_NAME``, Phase 87).
    """

    values = {
        "<": commander_name,
        ">": f"{commander_name}'s",
        "\\": weapon_name,
        "^R": race_name,
    }
    return render(WEAPON_RALLY_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _BNoEx -- a single, real, hardcoded precursor
# clause (no file, no trailing period -- SAY.PAS concatenates further
# content directly after it). See module docstring's Phase 126
# addendum, and the same bare-constant shape
# ``EXPLORE_NOT_PRESENT_PREFIX`` (Phase 110) already established.
DUEL_NO_EXCUSE_TEMPLATE = (
    "< couldn't/Rfailed_to think_of/Rcome_up_with a good/Rbelievable "
    "excuse/Rploy for_avoiding/Rto_get_out_of the duel, so "
)


# HostAK/TP/SAY.PAS _LChUnd -- a single, real, hardcoded template (no
# file). See module docstring's Phase 126 addendum.
VAMPIRIC_BITE_TEMPLATE = (
    "< sank/Rbit > fangs into [ and drained/Rsucked_up {all }] blood."
    "[1 changed to $o alignment!"
)


def render_vampiric_bite(
    attacker_name: str, victim_name: str, alignment_name: str, rng: random.Random
) -> str:
    """Renders ``_LChUnd``'s sentence: a vampiric bite that changes the
    victim's alignment. ``alignment_name`` is ``PROSE.TXT``'s own
    ``$o`` marker (already used by ``models/power.py``, Phase 95/101).
    """

    values = {
        "<": attacker_name,
        ">": f"{attacker_name}'s",
        "[": victim_name,
        "]": f"{victim_name}'s",
        "[1": victim_name,
        "$o": alignment_name,
    }
    return render(VAMPIRIC_BITE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS code 32500 -- a single, real, hardcoded template
# (no file). See module docstring's Phase 127 addendum.
ILLEGAL_MOVE_NON_ADJACENT_TEMPLATE = (
    "< tried to move from ^S to @, a non-adjacent province.This is illegal!"
)


def render_illegal_move_non_adjacent(
    character_name: str, origin_province_name: str, destination_province_name: str, rng: random.Random
) -> str:
    """Renders code ``32500``'s sentence: an illegal non-adjacent Move
    attempt -- ties to the non-adjacent-move chase concept (Phase
    78/85, rulebook [3.1]).
    """

    values = {
        "<": character_name,
        "^S": origin_province_name,
        "@": destination_province_name,
    }
    return render(ILLEGAL_MOVE_NON_ADJACENT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS code 32501's generic prefix -- a single, real,
# hardcoded template (no file). See module docstring's Phase 127
# addendum.
ILLEGAL_MOVE_ATTEMPTED_TEMPLATE = "< attempted an illegal move."


def render_illegal_move_attempted(character_name: str, rng: random.Random) -> str:
    """Renders code ``32501``'s generic prefix sentence, dispatched
    whenever ``_next <> 5`` -- precedes one of the sub-case sentences
    below.
    """

    values = {"<": character_name}
    return render(ILLEGAL_MOVE_ATTEMPTED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS code 32501's ``_next = -1`` sub-case -- a single,
# real, hardcoded template (no file). See module docstring's Phase 127
# addendum. Ties to turn/contested_province.py is_illegal_move_from_
# contested() (Phase 36).
ILLEGAL_MOVE_OCCUPIED_RETREAT_TEMPLATE = "< could not retreat into an occupied province."


def render_illegal_move_occupied_retreat(character_name: str, rng: random.Random) -> str:
    """Renders code ``32501``'s ``_next = -1`` sentence: a retreat into
    an occupied province was rejected.
    """

    values = {"<": character_name}
    return render(ILLEGAL_MOVE_OCCUPIED_RETREAT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS code 32501's ``_next`` 100..149 sub-case -- a
# single, real, hardcoded template (no file), the source's own
# "insufficent" spelling kept verbatim. See module docstring's Phase
# 127 addendum.
ILLEGAL_MOVE_INSUFFICIENT_WATER_TRANSPORT_TEMPLATE = (
    "< tried to use water-borne movement to move from ^S to @, "
    "but > transport was insufficent for the task."
)


def render_illegal_move_insufficient_water_transport(
    character_name: str, origin_province_name: str, destination_province_name: str, rng: random.Random
) -> str:
    """Renders code ``32501``'s ``_next`` 100..149 sentence: insufficient
    water-borne transport capacity.
    """

    values = {
        "<": character_name,
        "^S": origin_province_name,
        "@": destination_province_name,
        ">": f"{character_name}'s",
    }
    return render(ILLEGAL_MOVE_INSUFFICIENT_WATER_TRANSPORT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS code 32501's ``_next`` 150..199 sub-case -- a
# single, real, hardcoded template (no file). See module docstring's
# Phase 127 addendum.
ILLEGAL_MOVE_FLOODING_TRANSPORT_TEMPLATE = (
    "< tried to move from ^S to @, but provincial flooding and "
    "insufficient transport thwarted the move."
)


def render_illegal_move_flooding_transport(
    character_name: str, origin_province_name: str, destination_province_name: str, rng: random.Random
) -> str:
    """Renders code ``32501``'s ``_next`` 150..199 sentence: provincial
    flooding plus insufficient transport thwarted the Move.
    """

    values = {
        "<": character_name,
        "^S": origin_province_name,
        "@": destination_province_name,
    }
    return render(ILLEGAL_MOVE_FLOODING_TRANSPORT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS code 32501's ``_next`` 200..249 sub-case -- a
# single, real, hardcoded template (no file); "air-transport" for
# Mermen is the source's own literal text, transcribed verbatim rather
# than "corrected". See module docstring's Phase 127 addendum.
ILLEGAL_MOVE_MERMEN_AIR_TRANSPORT_TEMPLATE = (
    "< was ordered to move with Mermen from ^S to @, but had "
    "insufficient air-transport."
)


def render_illegal_move_mermen_air_transport(
    character_name: str, origin_province_name: str, destination_province_name: str, rng: random.Random
) -> str:
    """Renders code ``32501``'s ``_next`` 200..249 sentence: insufficient
    (Pascal source's own literal) "air-transport" for a Mermen Move.
    """

    values = {
        "<": character_name,
        "^S": origin_province_name,
        "@": destination_province_name,
    }
    return render(ILLEGAL_MOVE_MERMEN_AIR_TRANSPORT_TEMPLATE, values, rng=rng)


# HostAK/TP/PROSE/ILLMOVE.X2, verbatim, keyed by `_next+1` (`_next=0`
# aliases to choice 1, the same forced-index convention FD itself
# applies everywhere else -- see module docstring's Phase 127 addendum
# for the ELSE branch this completes). Choices 22-99 have no physical
# content in the source (header declares 99, only 22 rows exist) --
# choice 22 itself is not real game text either, a literal leftover
# author note ("Note: don't forget to increase #lines!! (this is line
# 22)"), so only 1-21 are transcribed. Choice 7's own real content is
# the literal string "xxxxxxxx" -- kept verbatim, an unfilled
# placeholder slot in the source itself, not a transcription gap.
# Same "raw file position, no semantic mapping asserted" posture
# NEMESIS_TEMPLATE already established: this project has no source
# tying any specific _next value in this range to a specific
# validation scenario, so none is guessed at.
ILLMOVE_TEMPLATE: dict[int, str] = {
    1: '< was ordered to move from ⟦CTRL-S:province-2⟧ to @, but it is illegal to move naval forces from one non-sea province to another.',
    2: '< was ordered to move with whales into @, a land province.This is illegal.',
    3: '< was ordered to move from ⟦CTRL-S:province-2⟧ to @, further than > army/Snavy could move.',
    4: '< was ordered to use water-borne movement to move from ⟦CTRL-S:province-2⟧ to @, but had no transport.',
    5: '< cancelled > move to @ in order to fight for the province of ⟦CTRL-S:province-2⟧.',
    6: "< was ordered to move into @ but couldn't because it is owned by [, a Neutral player-King.",
    7: 'xxxxxxxx',
    8: "< could not move to @ because you can't move to another King's province in a late move.",
    9: "< could not move to @ because you can't invade a province adjacent to another Kingdom in a late move.",
    10: '< was already in @ and could make no sense of the order to move to @.',
    11: "< could not move to @ because armies can't move overland and use transport in the same turn.",
    12: "< could not move to @ because armies can't use transport and move overland in the same turn.",
    13: "< could not move to @ because > fleets couldn't enter the parted sea.",
    14: "< could not move from ⟦CTRL-S:province-2⟧ to @ because > fleets couldn't leave the parted sea.",
    15: '< could not move from ⟦CTRL-S:province-2⟧ to @ because > mermen had insufficient air transport.',
    16: '< could not move from ⟦CTRL-S:province-2⟧ to @ because > ents refused to cross the shoreline.',
    17: "< could not move from ⟦CTRL-S:province-2⟧ to @'s terrain.",
    18: '< could not find a legal 2-province path to @.',
    19: '< could not move from ⟦CTRL-S:province-2⟧ to @ because > dinosaurs refused to cross the shoreline.',
    20: '< tried to move from ⟦CTRL-S:province-2⟧ to @, a non-adjacent province.Instead,_',
    21: "< couldn't move to @ because > non-flying armies couldn't move into a Lava province.",
}


# HostAK/TP/SAY.PAS _LHaHa -- a single, real, hardcoded template (no
# file), an unclosed quote transcribed honestly. See module
# docstring's Phase 129 addendum.
QUEST_MOCKERY_TEMPLATE = (
    'snarleth/Rchortled [1, "Ha!You fool/Rbumpkin, '
    "I've tricked/Rdeceived you!"
)


def render_quest_mockery(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LHaHa``'s sentence: the quest-giving monster mocks
    the character after tricking them.
    """

    values = {"[1": monster_name}
    return render(QUEST_MOCKERY_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LBThen -- a single, real, hardcoded precursor
# clause (no file, no trailing period). See module docstring's Phase
# 129 addendum, and the same bare-constant shape
# EXPLORE_NOT_PRESENT_PREFIX (Phase 110) already established.
QUEST_BUT_THEN_TEMPLATE = "But then "


# HostAK/TP/SAY.PAS _LWGrr/_LPrDie -- a real, two-``Say()`` entry (no
# file). See module docstring's Phase 129 addendum.
_MONSTER_THREAT_DEATH_TEMPLATES = (
    '[1 snarled/Rgrowled, "You impudent fool!I\'ll teach YOU to show some respect!',
    'now, prepare/Rget_ready to die/Rmeet_your_maker!"',
)


def render_monster_threat_death(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LWGrr``'s/``_LPrDie``'s two sentences: the monster's
    angry retort followed by a closing death threat. Concatenates both
    rendered sentences with no separator, the same shape established
    throughout this module (Phase 107, 116, 119, 121, 125, 126).
    """

    values = {"[1": monster_name}
    first = render(_MONSTER_THREAT_DEATH_TEMPLATES[0], values, rng=rng)
    second = render(_MONSTER_THREAT_DEATH_TEMPLATES[1], values, rng=rng)
    return first + second


# HostAK/TP/SAY.PAS _LWTake -- a single, real, hardcoded template (no
# file), an unclosed quote transcribed honestly. See module
# docstring's Phase 129 addendum.
QUEST_ITEM_TAKEN_ANYWAY_TEMPLATE = (
    'Sayeth [1, "{Ah, }thank you{ very much}.But I {will }always_TAKE/Rwrest_for_myself '
    "what I want/Rdesire!"
)


def render_quest_item_taken_anyway(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LWTake``'s sentence: the monster thanks the character
    but takes what it wants anyway.
    """

    values = {"[1": monster_name}
    return render(QUEST_ITEM_TAKEN_ANYWAY_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LWErrand -- a single, real, hardcoded template (no
# file), an unclosed quote transcribed honestly. See module
# docstring's Phase 129 addendum.
QUEST_ERRAND_THANKS_TEMPLATE = (
    'Sayeth [, "You have done/Rserved_me well/Radmirably{, and you have '
    "my thanks/Rgratitude}."
)


def render_quest_errand_thanks(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LWErrand``'s sentence: the monster thanks the
    character for a completed errand.
    """

    values = {"[": monster_name}
    return render(QUEST_ERRAND_THANKS_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFWrong -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_WRONG_ANSWER_TEMPLATE = (
    'Sayeth [, "No!That is not the answer I had_in_mind/Rwas_thinking_of.'
    "Why don't you give up{, you fool/Ridiot}?\""
)


def render_quest_wrong_answer(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFWrong``'s sentence: the character gave the wrong
    answer to the monster's own quest riddle/challenge.
    """

    values = {"[": monster_name}
    return render(QUEST_WRONG_ANSWER_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFProgr -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_PROGRESS_ACKNOWLEDGED_TEMPLATE = (
    'Sayeth [1, "You have served_me/Rdone well.I shall remember/Rnot_forget '
    'you{r kindness/Rdeed}."'
)


def render_quest_progress_acknowledged(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFProgr``'s sentence: the monster acknowledges the
    character's own quest progress.
    """

    values = {"[1": monster_name}
    return render(QUEST_PROGRESS_ACKNOWLEDGED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFNQual -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_INSUFFICIENT_SKILL_TEMPLATE = (
    'Sayeth [1, "You haven\'t the skill required/Rnecessary to do as '
    'I\'ve asked/Rrequested!Go away!"'
)


def render_quest_insufficient_skill(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFNQual``'s sentence: the character lacks the skill
    required for the quest.
    """

    values = {"[1": monster_name}
    return render(QUEST_INSUFFICIENT_SKILL_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFNoPri -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_INSUFFICIENT_PRICE_TEMPLATE = (
    'Sayeth [1, "You have not met/Rbrought_me my asking price{ at all}!Go away!"'
)


def render_quest_insufficient_price(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFNoPri``'s sentence: the character did not meet the
    monster's own asking price.
    """

    values = {"[1": monster_name}
    return render(QUEST_INSUFFICIENT_PRICE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFTryAg -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_SERVICE_NOT_PERFORMED_TEMPLATE = (
    'Sayeth [1, "You have not done_as/Rperformed_the_service I asked/Rwished'
    '{ at all}!Go away!"'
)


def render_quest_service_not_performed(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFTryAg``'s sentence: the character did not perform
    the requested service.
    """

    values = {"[1": monster_name}
    return render(QUEST_SERVICE_NOT_PERFORMED_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFKOnly -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_FLED_IN_FEAR_TEMPLATE = "But as < approached [, < lost > courage and ran away from [."


def render_quest_fled_in_fear(character_name: str, monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFKOnly``'s sentence: the character's own courage
    fails during the quest encounter and they flee.
    """

    values = {
        "<": character_name,
        "[": monster_name,
        ">": f"{character_name}'s",
    }
    return render(QUEST_FLED_IN_FEAR_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFHero -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_HERO_NOT_TASTY_TEMPLATE = (
    'Sayeth [1, "That one did not taste like a Hero!Next time bring me '
    'something tastier.Now, go away!"'
)


def render_quest_hero_not_tasty(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFHero``'s sentence: the monster rejects a Hero
    offering as unsatisfactory."""

    values = {"[1": monster_name}
    return render(QUEST_HERO_NOT_TASTY_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LFNoAg -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_NO_AGREEMENT_TEMPLATE = (
    'Sayeth [1, "Fulfill what?We have not talked over any agreement!Go away!"'
)


def render_quest_no_agreement(monster_name: str, rng: random.Random) -> str:
    """Renders ``_LFNoAg``'s sentence: no prior quest agreement ever
    existed.
    """

    values = {"[1": monster_name}
    return render(QUEST_NO_AGREEMENT_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LQDone -- a single, real, hardcoded template (no
# file). See module docstring's Phase 129 addendum.
QUEST_REWARD_ALREADY_GIVEN_TEMPLATE = (
    'Sayeth [1, "I have already given away the \\ to a worthier adventurer.Go away!"'
)


def render_quest_reward_already_given(monster_name: str, item_name: str, rng: random.Random) -> str:
    """Renders ``_LQDone``'s sentence: the quest reward was already
    given to another adventurer. ``item_name`` is ``PROSE.TXT``'s own
    ``\\`` (Magic Item) marker.
    """

    values = {"[1": monster_name, "\\": item_name}
    return render(QUEST_REWARD_ALREADY_GIVEN_TEMPLATE, values, rng=rng)


# HostAK/TP/PROSE/RIDDLE.X2 (header "7 2", RUMORS.PAS:2099 CTRL-G) and
# RANS.X (header "7 1", SAY.PAS:767 _LRidAns), both keyed by Treasure's
# own 7 QUEST_RA_* members -- module docstring's Phase 582 addendum.
# Stored as raw template text -- see that addendum for why (real
# CTRL-byte codes render() has no defined behavior for).
QUEST_RIDDLE_TEXT: dict[Treasure, str] = {
    Treasure.QUEST_RA_RIDDLE: '"\'I am ⟦CTRL-A:a/an⟧ monster, strange and alien.A band of hunters follows behind me looking for the tracks made by my feet.They desire greatly to put me to ⟦CTRL-A:a/an⟧ end, yet they seek no meat, only knowledge.i inhabit the darkest places, and if I pass from the shadows into the bright light my soul quickly slips away.What am I?\'',
    Treasure.QUEST_RA_COFFIN: '"Solve this riddle: $+$+There was ⟦CTRL-A:a/an⟧ man bespake a thing, $+Which when the bearer home did bring, $+He that brought it would not use it:$+and he that made it did refuse it, $+And he that hath it doth not know $+Whether he hath it, yea or no. $+$+',
    Treasure.QUEST_RA_BRIDGE: '"\'What thing is it, the weaker it is the more it is dread?\'',
    Treasure.QUEST_RA_CANDLE: '"\'What weeps tears without ⟦CTRL-A:a/an⟧ eye, and makes everything visible yet does not see?At the time when it approaches death, that which cuts off its head revives it.\'',
    Treasure.QUEST_RA_SMOKE: '"\'I am ⟦CTRL-A:a/an⟧ wingless bird, flying even to the clouds of heaven.I give birth to tears of mourning in pupils that meet me, and at once on my birth I am dissolved.What am I?\'',
    Treasure.QUEST_RA_OWNER: '"\'What am I, the more that I make ⟦CTRL-A:a/an⟧ woman cry the better she deems me to be?\'',
    Treasure.QUEST_RA_MAN: '"\'What goes on four legs in the morning, two at midday and three legs in the evening?\'',
}


QUEST_RIDDLE_ANSWER_TEXT: dict[Treasure, str] = {
    Treasure.QUEST_RA_RIDDLE: 'Sayeth [, "Yes, \'Riddle\' is the correct answer!You\'re very good at this game."',
    Treasure.QUEST_RA_COFFIN: 'Sayeth [, "\'Coffin\' is right.What a lucky guess!"',
    Treasure.QUEST_RA_BRIDGE: 'Sayeth [, "\'Bridge\' is the true answer.Hmm, you must have heard this riddle elsewhere."',
    Treasure.QUEST_RA_CANDLE: 'Sayeth [, "\'Candle\' is indeed what I had in mind.You\'re not as dumb as you look!"',
    Treasure.QUEST_RA_SMOKE: 'Sayeth [, "Yes, \'Smoke\' is the right answer.How did you ever guess this one?"',
    Treasure.QUEST_RA_OWNER: 'Sayeth [, "You got it, \'Onion\' is right.But it took you LONG ENOUGH to solve it!Hah!"',
    Treasure.QUEST_RA_MAN: 'Sayeth [, "Yes!\'Man\' is the right answer, as recorded by Greek mythology (which you must be well-acquainted with.)"',
}


# HostAK/TP/PROSE/VISIT.X2 (header "5 2", RUMORS.PAS:2098 CTRL-U) and
# FUVIS.X2 (header "5 1", SAY.PAS:785 _LFuVis), both keyed by Treasure's
# own 5 non-riddle "go somewhere and do something" quest-item members --
# module docstring's Phase 582 addendum.
QUEST_VISIT_TEXT: dict[Treasure, str] = {
    Treasure.QUEST_SNOW_QUEST: 'there towers ⟦CTRL-A:a/an⟧ raging volcano which is about to erupt and incinerate the world with its fiery lava.And the northern and southern icecaps are expanding, threatening to blanket the world in ice!go to ⟦CTRL-A:a/an⟧ province next to ⟦CTRL-A:a/an⟧ icecap and make a snowball.Then, travel to ⟦CTRL-X:province-3⟧ and throw it in!Only thusly can the Cosmic Balance be set aright and the world be saved!',
    Treasure.QUEST_SAPPH_RING: 'there stands ⟦CTRL-A:a/an⟧ ancient, long-dead volcano whose crater has been filled with water so blue and sparkling, it is like ⟦CTRL-A:a/an⟧ great sapphire.According to lore, it is the deepest lake in the world."[1 slipped ] ring off a finger."this ring reminds me of ⟦CTRL-A:a/an⟧ deep, long-lost love whom I must forget, and the lake is its only fitting place of rest in the whole world.Take then this ring and cast it into the lake, that my sorrow may also be set at rest!',
    Treasure.QUEST_LUCKY_PENNY: 'the province of my birth, there is ⟦CTRL-A:a/an⟧ wishing-well which I remember from my younger days.For me, it is the luckiest well in the world.You see, for years I have been having bad luck.take my lucky penny and journey to the well.When you get there, wish me luck and toss it into the well.Then, maybe my luck will change!',
    Treasure.QUEST_GODS_QUEST: 'the inhabitants are said to worship strange gods.Go there and find out all you can about these gods, so that I may decide whether I may righteously devote myself to them and entreat them with my prayers.',
    Treasure.QUEST_MERMAID_AMULET: 'there are waters where mermaids have been known to frolic.I must confess to ⟦CTRL-A:a/an⟧ special weakness for these fair-finned creatures.Fortunately, I have a magic amulet which, I am told, will charm one more mermaid before it loses its magic.go to ⟦CTRL-X:province-3⟧, charm ⟦CTRL-A:a/an⟧ mermaid for me and bring her back!',
}


QUEST_VISIT_FULFILLED_TEXT: dict[Treasure, str] = {
    Treasure.QUEST_SNOW_QUEST: 'While < was in @, < found the raging volcano and threw in the Cosmic Snowball.< thought < sensed a quietening of the volcano; or, perhaps it just something < imagined.',
    Treasure.QUEST_SAPPH_RING: 'While < was in @, < found an ancient, long-dead volcano whose crater had been filled with incredibly blue and sparkling water.< took the Sapphire Ring and, with a twinge of sorrow, cast it into the lake.',
    Treasure.QUEST_LUCKY_PENNY: 'While < was in @, < found ⟦CTRL-A:a/an⟧ wishing-well which matched the description < had been given.< took the Lucky Penny, wished for luck and tossed it into the well.',
    Treasure.QUEST_GODS_QUEST: 'While < was in @, < investigated the strange gods worshipped there.Some were strange hybrids between men and animals, and one even looked like a giant rat!Shaking > head in disbelief, < wrote down descriptions of all these bizarre gods.',
    Treasure.QUEST_MERMAID_AMULET: 'While < was in @, < found waters where frolicked many beautiful mermaids.Invoking the magic amulet, < charmed a comely mermaid and resolved to bear her flirtations until they could return to fulfill the quest.',
}


# HostAK/TP/RUMORS.PAS Check_Raid -- a single, real, hardcoded
# template (no file), dispatched inline within FD's own MTALK.X2
# file-dispatch flow rather than the main Say_Code CASE. See module
# docstring's Phase 130 addendum.
MONSTER_OFFERS_RAID_TRUCE_TEMPLATE = (
    "[ also offered to stop raiding/Rplundering @ if this quest "
    "be/Rwere accomplished/Rcompleted."
)


def render_monster_offers_raid_truce(monster_name: str, province_name: str, rng: random.Random) -> str:
    """Renders ``Check_Raid``'s sentence: a guarding monster whose own
    ``fstate`` is ``Bold`` (``models/monster.py
    MonsterEngagementState.BOLD``, "Emboldened", Phase 130) offers to
    stop raiding a province if its quest is fulfilled.
    """

    values = {"[": monster_name, "@": province_name}
    return render(MONSTER_OFFERS_RAID_TRUCE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LTrade -- a single, real, hardcoded template (no
# file). See module docstring's Phase 133 addendum.
ITEM_GIVE_TEMPLATE = "< gave the \\ to [."


def render_item_give(giver_name: str, recipient_name: str, item_name: str, rng: random.Random) -> str:
    """Renders ``_LTrade``'s sentence: a successful magic-item Give
    (rulebook [3.18]), ``turn/trade_execution.py execute_give()``'s own
    item path -- real as of Phase 140's item-ownership registry. See
    ``describe_give()`` below for the composer that actually consumes a
    real ``TradeExecutionResult`` to decide when this renders.
    """

    values = {"<": giver_name, "[": recipient_name, "\\": item_name}
    return render(ITEM_GIVE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LGGive -- a single, real, hardcoded template (no
# file). See module docstring's Phase 133 addendum.
GOLD_GIVE_TEMPLATE = "< gave/Rdonated to [ # gold from > treasury/Rown_funds."


def render_gold_give(giver_name: str, recipient_name: str, gold_amount: int, rng: random.Random) -> str:
    """Renders ``_LGGive``'s sentence: a successful gold Give -- ``turn/
    trade_execution.py execute_give()``'s own success case.
    """

    values = {"<": giver_name, "[": recipient_name, "#": str(gold_amount), ">": f"{giver_name}'s"}
    return render(GOLD_GIVE_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LNHave -- a single, real, hardcoded template (no
# file). Transcribed as-is, including its trailing "so " -- no
# continuation is found anywhere else in the available source, the
# same honest-fragment-transcription convention as Phase 129's
# _LHaHa/_LWTake/_LWErrand. See module docstring's Phase 133 addendum.
INSUFFICIENT_GOLD_TEMPLATE = "< didn't have on hand the full # gold requested, so "


def render_insufficient_gold(giver_name: str, gold_requested: int, rng: random.Random) -> str:
    """Renders ``_LNHave``'s (fragment) sentence: the giver's treasury didn't hold
    enough gold to cover the requested amount -- ``turn/
    trade_execution.py execute_give()``'s own 10%-cap failure case.
    """

    values = {"<": giver_name, "#": str(gold_requested)}
    return render(INSUFFICIENT_GOLD_TEMPLATE, values, rng=rng)


# HostAK/TP/SAY.PAS _LNDeal -- a single, real, hardcoded template (no
# file). See module docstring's Phase 133 addendum.
TRADE_DEAL_FAILED_TEMPLATE = "< could not strike a deal with [ for the \\."


def render_trade_deal_failed(giver_name: str, recipient_name: str, item_name: str, rng: random.Random) -> str:
    """Renders ``_LNDeal``'s sentence: a reciprocal two-way trade's condition wasn't met
    (rulebook [3.18]: "the gift will be made only if the recipient
    Gives you a specified magic item... in the same phase").

    **Not called by ``describe_give()`` below**: the reciprocal
    two-way-trade condition this renders has no execution-side
    trigger anywhere in this project -- ``turn/trade_decode.py``'s own
    docstring confirms only the giver's own single item-or-gold amount
    is decoded, never a recipient-side reciprocal item id, so
    ``execute_give()`` has no state from which to ever produce this
    outcome. Kept here, rendered directly by a future caller, the same
    way this project keeps other genuinely-sourced-but-unwired
    renderers rather than deleting them.
    """

    values = {"<": giver_name, "[": recipient_name, "\\": item_name}
    return render(TRADE_DEAL_FAILED_TEMPLATE, values, rng=rng)


def describe_give(
    result: TradeExecutionResult,
    *,
    giver_name: str,
    recipient_name: str,
    item_name: str | None = None,
    gold_requested: int | None = None,
    rng: random.Random,
) -> str | None:
    """Assembles the one-sentence Give narrative from an already-computed
    ``TradeExecutionResult`` (``turn/trade_execution.py execute_give()``,
    Phase 133, item path closed Phase 140) -- the same "data first,
    already-computed result in, prose out" pattern ``describe_battle()``
    above already established for battle outcomes.

    - A successful item transfer (``result.item_transferred``) renders
      ``_LTrade`` -- needs a caller-supplied ``item_name``. As of Phase
      214, ``describe_turn_results()`` resolves this itself via
      ``models/treasure.py TREASURE_NAME[result.item.treasure]``
      (``result.item`` is the real transferred ``ItemInstance``, now
      kept on ``TradeExecutionResult``); a direct caller with no
      ``TradeExecutionResult.item`` still needs to supply ``item_name``
      itself, and gets ``None`` back without one rather than a guess.
    - A successful gold transfer (``result.gold_transferred > 0``)
      renders ``_LGGive``.
    - A failure specifically because the giver's treasury didn't cover
      [3.18]'s 10%-cap (``execute_gold_give()``'s own
      ``"exceeds 10% treasury cap"`` reason string) renders ``_LNHave``
      -- needs a caller-supplied ``gold_requested`` (the original
      decoded amount, not the cap itself); returns ``None`` without one.
    - Every other failure reason (giver/recipient not found, not
      co-located, recipient not a King, no recipient decoded) has no
      sourced narrative template at all and renders nothing -- this
      project doesn't invent administrative-error prose.
    """

    if result.applied and result.item_transferred:
        if item_name is None:
            return None
        return render_item_give(giver_name, recipient_name, item_name, rng)

    if result.applied and result.gold_transferred > 0:
        return render_gold_give(giver_name, recipient_name, result.gold_transferred, rng)

    if not result.applied and result.reason is not None and result.reason.startswith("exceeds 10% treasury cap"):
        if gold_requested is None:
            return None
        return render_insufficient_gold(giver_name, gold_requested, rng)

    return None


# HostAK/TP/PROSE/FRUMOR.X -- the rumor narrative (Phase 243's own
# resolve_rumor_generation()). The real Pascal sentence always names
# *both* the guardian and the treasure in one clause ("& inhabited by
# +, who guards the \") -- but Phase 243's own confirmed design reveals
# only one of the two per rumor (70% monster, 30% item). Adapted per
# the user's own confirmed resolution to this conflict: every clause
# that doesn't touch the omitted detail stays verbatim (including the
# source's own double-space idiosyncrasies), only the tail clause
# naming the omitted detail is dropped/replaced. Two variant sets, not
# one, as a result -- FRUMOR.X's own 4 sentences, each split in two.
_FRUMOR_MONSTER_TEMPLATES: list[str] = [
    "{While carousing/Rdrinking with fellow/Rother adventurers/Rtravellers in a bar/Rtavern, }< heard {mention/Rtell "
    "}of a{n interesting} feature in  $#:  & inhabited/Roccupied by +.",
    "{While }conversing/Rspeaking with {passing/Rfriendly }merchants/Radventurers, < heard/Rlearned a rumor about  "
    "previously/Rheretofore unknown/Runheard_of & in  $#, held/Rinhabited by +.",
    "< heard a rumor telling of  {perilous }feature in  $#{ previously unknown to us},  & inhabited_by/Rwhere_dwells +.",
    "{while }talking/Rspeaking to some {friendly }locals/Rfarmers, < heard a rumor about  & in  $#, "
    "occupied/Rinhabited by +.",
]

_FRUMOR_ITEM_TEMPLATES: list[str] = [
    "{While carousing/Rdrinking with fellow/Rother adventurers/Rtravellers in a bar/Rtavern, }< heard {mention/Rtell "
    "}of a{n interesting} feature in  $#:  & is said/Rrumored to hold the \\.",
    "{While }conversing/Rspeaking with {passing/Rfriendly }merchants/Radventurers, < heard/Rlearned a rumor about  "
    "previously/Rheretofore unknown/Runheard_of & in  $#, reputed/Rsaid to contain the \\.",
    "< heard a rumor telling of  {perilous }feature in  $#{ previously unknown to us},  the & is reputed to "
    "contain the \\.",
    "{while }talking/Rspeaking to some {friendly }locals/Rfarmers, < heard a rumor about  & in  $#. "
    "They/Rsome say/Rmaintain that the & holds the \\.",
]


def describe_rumor(rumor: Rumor, state: GameState, character_name: str, board_width: int, rng: random.Random) -> str:
    """Assembles the one-sentence Rumor narrative from an already-generated
    ``Rumor`` (``turn/rumor.py resolve_rumor_generation()``, Phase 243).

    Unlike ``describe_give()``/``describe_hire()``, this takes ``state``
    directly (matching ``describe_bystander_spell_notice()``'s own
    "needs to re-resolve a coordinate" precedent) rather than plain
    caller-supplied strings for every field: the feature's own *kind*
    is never falsified by Phase 243's own design (only the guardian/
    treasure/province can be), so it's always looked up straight from
    ``state.features[rumor.feature_id]`` rather than threaded through
    ``Rumor`` itself. ``#`` (`report/prose.py`'s own "a number" marker)
    renders the raw hex location code FRUMOR.X's own ``$#`` uses for an
    unvisited province (the ``$`` is a literal character already in the
    template, matching Pascal's own hex-literal notation, not a second
    marker) -- ``turn/hex_numbering.py encode_hex_number()``, the exact
    inverse of the decode every LMOVE order already uses.

    Dispatches on ``rumor.content`` (``RumorContent.FEATURE_AND_MONSTER``
    -> ``MONSTER_NAMES[rumor.described_monster]``, ``RumorContent.ITEM``
    -> ``TREASURE_NAME[rumor.described_treasure]``) -- exactly one of the
    two ever gets named, per this module's own Phase 244 addendum above.
    Prints whatever ``rumor`` says without regard to ``rumor.is_true``:
    a false rumor is supposed to read exactly like a true one to the
    kingdom that heard it, that's the entire point of it being false.
    """

    feature = state.features[rumor.feature_id]
    feature_name = FEATURE_TYPE_NAMES[feature.kind]
    location_code = str(encode_hex_number(rumor.described_coord, board_width))
    values = {"<": character_name, "&": feature_name, "#": location_code}
    if rumor.content is RumorContent.FEATURE_AND_MONSTER:
        values["+"] = MONSTER_NAMES[rumor.described_monster]
        variant = pick_variant(_FRUMOR_MONSTER_TEMPLATES, rng)
    else:
        values["\\"] = TREASURE_NAME[rumor.described_treasure]
        variant = pick_variant(_FRUMOR_ITEM_TEMPLATES, rng)
    return render(variant, values, rng=rng)


# HostAK/TP/PROSE/FINDFEAT.X -- the in-person discovery narrative
# (Phase 245), FRUMOR.X's own sibling: a character physically standing
# in the province, so the real template uses "@" (resolved province
# name) rather than FRUMOR.X's "$#" (raw hex number for an unvisited
# one). Unlike FRUMOR.X, the real sentence never mentions a treasure at
# all -- only the feature and its guardian monster -- so this is a
# straight, unmodified 4-variant transcription, no FRUMOR.X-style
# adapt-and-split needed. Quoted in full:
#   < discovered/Rfound a{n interesting} feature in @:  &  inhabited/Roccupied by +.
#   < discovered/Rlocated  previously/Rheretofore unknown/Runheard_of &  in @, held/Rinhabited by +.
#   < was informed/Rtold by some peasants/Rsheepherders of  {perilous }feature in @{ previously unknown to us},  &  inhabited_by/Rwhere_dwells +.
#   < {also }found/Rdiscovered  &  in @, occupied/Rinhabited by +.
_FINDFEAT_TEMPLATES: list[str] = [
    "< discovered/Rfound a{n interesting} feature in @:  &  inhabited/Roccupied by +.",
    "< discovered/Rlocated  previously/Rheretofore unknown/Runheard_of &  in @, held/Rinhabited by +.",
    "< was informed/Rtold by some peasants/Rsheepherders of  {perilous }feature in @{ previously unknown to us},  "
    "&  inhabited_by/Rwhere_dwells +.",
    "< {also }found/Rdiscovered  &  in @, occupied/Rinhabited by +.",
]


def render_monster_description(monster: Monster) -> str:
    """Renders MONSTERS.X2's own flavor-text sentence(s) for ``monster``
    (Phase 613) -- rulebook [3.2]'s own line, "Monsters are described
    when they are first discovered" (``SAY.PAS:790 _LMDesc``). Plain
    verbatim text, no ``render()`` needed: not one of ``MONSTER_
    DESCRIPTION``'s own 60 real entries carries a ``/R``/``{}`` choice
    marker (confirmed by grep), so there's nothing to vary and no
    ``rng`` parameter, the same "nothing to vary" shape ``render_magic_
    feature_discovery()`` already established.

    "First discovered" is read here as *this in-person discovery
    event* (the same moment ``describe_feature_discovery()`` itself
    fires from, immediately below) rather than "the first time this
    Kingdom has ever seen this monster species" -- the rulebook gives
    no threshold, and this project has no per-Kingdom "monster species
    already seen" tracking anywhere to gate a stricter reading on
    (confirmed absent by grep) -- inventing one would be exactly the
    kind of unsourced state-tracking mechanism this project's own "no
    source, no guess" discipline avoids. If a real source ever
    surfaces confirming the stricter "once per species" reading, this
    is the one place to revisit.
    """

    return MONSTER_DESCRIPTION[monster]


def describe_feature_discovery(feature: Feature, character_name: str, province_name: str, rng: random.Random) -> list[str]:
    """Renders FINDFEAT.X's sentence for a feature just found in person --
    ``turn/exploration.py discover_features()`` (Phase 242), now surfaced
    to a caller via ``turn/move_execution.py KingdomExplorationResult``/
    ``report/turn_report.py ExploreResult.discovered_features`` (Phase
    245, closing the "record exists, no consumer yet" gap the EXPLORE
    dispatch branch left open since Phase 242).

    Assumes ``feature.guardian_monster`` is set -- true for every
    feature ``turn/world_generation.py`` ever creates (Phase 242
    confirmed every generated feature always gets a guardian), and the
    real template never has a treasure-only branch to fall back to
    (unlike FRUMOR.X's own rumor sentence, Phase 244) -- a feature built
    by a test or caller with no guardian isn't a valid input here.

    Returns two lines as of Phase 613: FINDFEAT.X's own discovery
    sentence, then ``render_monster_description()``'s own MONSTERS.X2
    flavor text for the guardian -- two separate ``SAY.PAS`` dispatch
    calls (``_LFind``/``_LMDesc``), not one concatenated fragment (see
    that function's own docstring for the "which discovery event"
    judgment call this rests on).
    """

    feature_name = FEATURE_TYPE_NAMES[feature.kind]
    monster_name = MONSTER_NAMES[feature.guardian_monster]
    values = {"<": character_name, "@": province_name, "&": feature_name, "+": monster_name}
    variant = pick_variant(_FINDFEAT_TEMPLATES, rng)
    return [render(variant, values, rng=rng), render_monster_description(feature.guardian_monster)]


# HostAK/TP/PROSE/FSEARCH.X -- the Search-attempt opening sentence. See
# module docstring's Phase 156 addendum.
_FSEARCH_TEMPLATES: list[str] = [
    "< approached/Rinvestigated the &, intending/Rmeaning to root_out/Runcover its mysteries/Sdark_secrets.",
    "< searched/Rapproached the & with every/Rthe intention of overcoming/Rprevailing_over it and whatever "
    "{vile }guardian {beast }lay within{ it}.",
    "< unsheathed/Rgirded > weapon and entered the & warily/Rcautiously.",
    "< downed/Rtook ^A {deep/Rlarge, }nervous draught/Rgulp from > flask/Rbottle of {old }vodka/Rscotch, "
    "and entered/Rapproached the &.",
    "< gathered > courage {and > wits }and {cautiously/Rnervously }entered the &.",
]


def render_search_attempt(character_name: str, feature_name: str, rng: random.Random, *, is_sea: bool = False) -> str:
    """Renders FSEARCH.X's sentence for the Search-attempt opening moment
    (``SAY.PAS`` ``_LSearch: FD('fsearch',S_Adv,10)``). ``feature_name``
    is ``PROSE.TXT``'s own ``&`` marker (Feature name -- ``report/
    prose.py``'s own marker table). ``is_sea`` (Phase 74) resolves the
    "/S" marker the first variant carries.
    """

    variant = pick_variant(_FSEARCH_TEMPLATES, rng)
    values = {"<": character_name, ">": f"{character_name}'s", "&": feature_name}
    return render(variant, values, rng=rng, is_sea=is_sea)


# HostAK/TP/SAY.PAS _LSacked -- a single, real, hardcoded template (no
# file). See module docstring's Phase 156 addendum.
SEARCH_FEATURE_ALREADY_SACKED_TEMPLATE = (
    "< searched/Rscouted_out the & but it {apparently }had {already }been looted/Rsacked."
)


def render_search_feature_already_sacked(character_name: str, feature_name: str, rng: random.Random) -> str:
    """Renders ``_LSacked``'s sentence for attempting to Search a feature
    that's already been looted (``turn/search_execution.py
    execute_search()``'s own ``"feature already looted"`` rejection).
    """

    values = {"<": character_name, "&": feature_name}
    return render(SEARCH_FEATURE_ALREADY_SACKED_TEMPLATE, values, rng=rng)


def describe_search(
    result: SearchExecutionResult,
    *,
    state: GameState | None = None,
    character_name: str,
    feature_name: str,
    rng: random.Random,
    is_sea: bool = False,
) -> list[str]:
    """Assembles Search's own turn-report lines from an already-computed
    ``SearchExecutionResult`` (``turn/search_execution.py
    execute_search()``, Phase 132/154/155), the same "data first,
    already-computed result in, prose out" pattern every other
    ``describe_*`` composer here already establishes.

    - Rejected specifically because the feature was already looted
      (``result.reason == "feature already looted"``) renders
      ``_LSacked`` alone (``render_search_feature_already_sacked()``) --
      the one rejection reason with a real sourced sentence. Every
      other rejection (leader/feature not found, no guardian recorded,
      not co-located) is an internal/engine-level state check, not a
      narrative moment the rulebook describes -- renders nothing, same
      "don't invent administrative-error prose" policy ``describe_give()``
      already states explicitly.
    - Every accepted attempt opens with ``_LSearch``/``FSEARCH.X``
      (``render_search_attempt()``), regardless of whether combat ever
      resolves -- the sentence describes *approaching* the feature, not
      its outcome.
    - **Phase 175: each Fire Arrow shot in ``result.fire_arrow_shots`` is
      narrated individually**, in order, right after the opening line.
      Only the guardian's own shots (``shot.shooter == "b"``, matching
      ``turn/encounter.py EncounterCombatResult``'s own "a"/"b" convention
      where ``a``=leader/``b``=monster, ``turn/search_execution.py``'s own
      Phase 175 addendum) are checked against ``missile_attack_flavor(
      MONSTER_RANGED_WEAPON.get(result.guardian_monster))`` for a species-
      specific dragon-breath/boulder-throw/petrifying-gaze sentence
      (Phase 155's renderers, previously never called from anywhere); the
      leader's own shots (``shooter == "a"``) always use the generic
      ``render_fire_arrow_attack()``/``render_attack_hit()``/
      ``render_attack_missed()`` triplet (Phase 111-112), per the user's
      own footnote wording ("cosa viene scritto quando parte il missile
      [del mostro]" -- what gets written when the monster's own missile
      is fired) -- the flavor describes what the *monster* does, never
      the character. A monster with no flavor mapping (``missile_attack_
      flavor()`` returns ``None`` -- includes Titan/Treant, ``models/
      weapon.py``'s own deliberately-preserved discrepancy, see that
      module's Phase 94 addendum) also falls back to the generic triplet
      for its own shots.
    - A fatal loss (``combat_resolved and winner == "monster" and
      leader_killed``) appends ``render_mortally_wounded()`` -- the same
      already-sourced MORTWOUN.X sentence (Phase 112) every other
      personal-combat death already uses, since [5.0]'s generic
      "until one combatant is killed" rule applies here exactly as
      ``turn/search_execution.py``'s own docstring already states --
      then (Phase 611) ``render_character_death()``, HORDEATH.X's own
      generic closing beat (see ``describe_encounter_combat()``'s own
      Phase 611 note for the sourcing).
    - A win (``winner == "leader"``, ``feature_looted``) or an
      inconclusive fight (``winner is None``) append nothing further
      beyond any shot narration above: no sourced sentence for "you
      defeated the guardian and the treasure is yours" exists anywhere
      in the available archive -- confirmed absent by the same research
      that found Phase 148's own skill-book-read gap (`TREASAB.X2`/
      `TREASURE.X2` are inventory-view text, not a Search-victory
      narration), not merely unsearched.
    - **Phase 413: each round of a winning Hand of Death channel
      (``result.squeeze_hits``) is narrated individually**, right after
      the Fire Arrow shots above, via ``render_squeeze_attack()`` +
      ``render_attack_hit()`` (Hand of Death's own attack always lands,
      so ``render_attack_missed()`` never applies). Whichever side cast
      the winning channel is read straight off ``result.winner`` --
      ``squeeze_hits`` is only ever populated for a winning channel (see
      ``SearchExecutionResult.squeeze_hits``'s own Phase 413 note for
      why an interrupted, non-winning channel isn't captured here).
    - **Phase 415: each ordinary Melee swing (``result.melee_swings``) is
      narrated individually**, right after the Hand of Death/Squeeze
      narration above, via ``render_melee_attack()`` (``SWANGAT.X``,
      Phase 113 -- built but never called from anywhere until this
      phase) + ``render_attack_hit()``/``render_attack_missed()``. Each
      ``MeleeSwing`` already carries its own ``attacker`` (``"a"``/
      ``"b"``), unlike Squeeze's one-directional ``result.winner``
      convention, since ordinary Melee is genuinely bidirectional round
      to round. ``attack_method`` (``PROSE.TXT``'s own ``$S`` marker)
      has no source anywhere in this project -- no per-character weapon
      model exists (``turn/encounter.py Combatant`` carries no weapon
      field) -- so every swing uses the fixed, project-original
      ``_MELEE_ATTACK_METHOD = "Attacked"`` default rather than a
      guessed sourced verb; see that constant's own Phase 415 note.

    **Phase 213: now wired into ``describe_turn_results()``.**
    ``SearchExecutionResult`` gained a ``request`` field (stamped by
    ``plan_dispatch.py _dispatch_search()``), resolving ``feature_id`` ->
    ``GameState.features`` -> a coordinate-based ``feature_name`` (this
    project has no per-feature display-name system, unlike provinces --
    see ``describe_turn_results()``'s own Phase 213 note). Callers with
    direct access to the original ``SearchRequest``/``Feature`` can still
    call this composer directly instead.
    """

    if not result.accepted:
        if result.reason == "feature already looted":
            return [render_search_feature_already_sacked(character_name, feature_name, rng)]
        return []

    lines = [render_search_attempt(character_name, feature_name, rng, is_sea=is_sea)]

    monster_name = MONSTER_NAMES.get(result.guardian_monster, "guardian") if result.guardian_monster is not None else "guardian"
    weapon = MONSTER_RANGED_WEAPON.get(result.guardian_monster) if result.guardian_monster is not None else None
    flavor = missile_attack_flavor(weapon) if weapon is not None else None

    for shot in result.fire_arrow_shots:
        if shot.shooter == "b" and flavor == "breath_weapon":
            lines.append(
                render_breath_weapon_hit(monster_name, character_name, shot.damage, rng)
                if shot.hit
                else render_breath_weapon_missed(monster_name, character_name, rng)
            )
        elif shot.shooter == "b" and flavor == "boulder_throw":
            lines.append(
                render_boulder_throw_hit(monster_name, character_name, shot.damage, rng)
                if shot.hit
                else render_boulder_throw_missed(monster_name, character_name, rng)
            )
        elif shot.shooter == "b" and flavor == "petrifying_gaze":
            lines.append(
                render_petrifying_gaze_hit(monster_name, character_name, shot.damage, rng)
                if shot.hit
                else render_petrifying_gaze_missed(monster_name, character_name, rng)
            )
        else:
            attacker_name, defender_name = (monster_name, character_name) if shot.shooter == "b" else (character_name, monster_name)
            attack_line = render_fire_arrow_attack(attacker_name, defender_name, rng)
            attack_line += (
                render_attack_hit(defender_name, shot.damage, rng)
                if shot.hit
                else render_attack_missed(attacker_name, defender_name, "arrow", rng, is_sea=is_sea)
            )
            lines.append(attack_line)

    # Phase 413: each round of a winning Hand of Death channel, narrated
    # individually via render_squeeze_attack() -- the caster's own attack
    # always lands (turn/encounter.py resolve_hand_of_death_channel()'s
    # own docstring), so every entry here always pairs with
    # render_attack_hit(), never render_attack_missed(). Whichever side
    # cast the winning channel is read off result.winner itself (only a
    # winning channel ever populates squeeze_hits at all -- see
    # SearchExecutionResult.squeeze_hits's own Phase 413 note).
    squeeze_attacker, squeeze_defender = (
        (monster_name, character_name) if result.winner == "monster" else (character_name, monster_name)
    )
    for damage in result.squeeze_hits:
        lines.append(render_squeeze_attack(squeeze_attacker, squeeze_defender, rng) + render_attack_hit(squeeze_defender, damage, rng))

    # Phase 415: each Melee swing (result.melee_swings, chronological
    # across every round actually fought at melee range) narrated
    # individually via render_melee_attack() (SWANGAT.X, Phase 113 --
    # built but never called from anywhere until now) + render_attack_
    # hit()/render_attack_missed(). Unlike squeeze_hits (one-directional,
    # tied to result.winner), each MeleeSwing already carries its own
    # attacker ("a"/"b") -- ordinary Melee is genuinely bidirectional
    # round to round, so there's no single "the attacker" to read off
    # result.winner here.
    for swing in result.melee_swings:
        melee_attacker, melee_defender = (
            (character_name, monster_name) if swing.attacker == "a" else (monster_name, character_name)
        )
        attack_line = render_melee_attack(melee_attacker, melee_defender, _MELEE_ATTACK_METHOD, rng)
        attack_line += (
            render_attack_hit(melee_defender, swing.damage, rng)
            if swing.hit
            else render_attack_missed(melee_attacker, melee_defender, "blade", rng, is_sea=is_sea)
        )
        lines.append(attack_line)

    if result.combat_resolved and result.winner == "monster" and result.leader_killed:
        lines.append(render_mortally_wounded(character_name, rng, is_sea=is_sea))
        lines.append(render_character_death(character_name, rng))

    # Phase 616: Scout's own Feature -> Power [5.8] outcome, narrated last
    # -- matches the rulebook's own "the computer will simply do your
    # Scout tactic after all other encounter tactics are completed"
    # (quoted in full in `_apply_scout()`'s own docstring). `None` covers
    # every outcome this phase has no recovered POWMSG.X2 id for (see
    # `describe_feature_power_attempt()`'s own docstring) as well as "no
    # Scout discovery this Search happened at all".
    if result.feature_power_outcome is not None:
        power_line = describe_feature_power_attempt(
            result.feature_power_outcome, rng, state=state, character_name=character_name
        )
        if power_line is not None:
            lines.append(power_line)
    return lines


# HostAK/TP/PROSE/QUOTES.X2 + HostAK/TP/SAY.PAS _SQuote. See
# models/quote.py's own module docstring for the full sourcing and the
# documented "real mechanism, uncomputable real-calendar trigger" split.
def render_quote_of_the_week(index: int) -> list[str]:
    """Renders the "Quote of the Week:" header plus the two source lines
    of :func:`ak_engine.models.quote.quote_of_the_week`'s own block
    ``index`` (0-93), as three separate paragraphs -- matching
    ``_SQuote``'s own ``Say('Quote of the Week:',S_Red)`` header
    followed by ``FD``'s per-line ``PR1`` paragraph break for a
    ``quotes.x2`` block (see the module docstring cited above). Neither
    line is passed through :func:`ak_engine.report.prose.render`: the
    real source data contains none of that engine's marker characters
    (confirmed empirically against all 94 blocks), so marker resolution
    would be a pure no-op here.

    The caller supplies ``index`` directly rather than this function
    computing a calendar-driven rotation itself -- see
    ``models/quote.py``'s own docstring for why ``_SQuote``'s real
    ``qfact`` formula can't be reproduced from a parsed move file alone.
    """

    quote_line, attribution_line = quote_of_the_week(index)
    return ["Quote of the Week:", quote_line, attribution_line]


# HostAK/TP/REPORTS.PAS Desc_Lands's own real "STATE OF THE NATION:"
# header + one fixed flavor paragraph (Phase 561) -- AKGEN_reverse_
# engineering_report (5).md SS29.1/SS86.2: `Desc_Lands` prints this
# unconditionally, immediately before DIPLOMACY, regardless of whether
# an Emperor exists (only IMPERIAL OFFICE REPORT's own position moves
# around it -- see describe_imperial_office_report()'s own docstring
# and compose_letter_report()'s own assembly for that half). Verified
# byte-for-byte identical across 6 real sample files this phase
# (Desktop's own SE3__T1.K2/T2.K1/T2.K2/T2.K3/T3.K2/T5.K2, none with
# an Emperor yet) -- this project's own composer never emitted this
# section at all before now.
_STATE_OF_THE_NATION_HEADER = "STATE OF THE NATION:"
_STATE_OF_THE_NATION_INTRO = (
    "My lord and sovereign, greatest of Kings, I humbly beg thy leave to make "
    "report of matters of this Kingdom that may concern thy divine majesty."
)


def describe_state_of_the_nation_report() -> list[str]:
    """The real "STATE OF THE NATION:" section -- see the module-level
    comment above this function for the full sourcing. Entirely fixed
    text, no `state`/`kingdom_id` needed -- the same "Kingdom-agnostic
    composer" shape `describe_alignment_victory_point_reduction(state)`
    already uses (that one still needs `state`, for the Emperor's own
    Alignment; this one needs nothing at all).
    """

    return [_STATE_OF_THE_NATION_HEADER, _STATE_OF_THE_NATION_INTRO]


# HostAK/TP/REPORTS.PAS Desc_Lands's own Rep_Allies/Begin_List (~line
# 104-119) -- the real "DIPLOMACY" section's own sourced, verbatim
# intro sentences (each rejoined across its own 2 raw WRITELN lines,
# same convention as _ARMIES_REPORT_OPENING) and empty-list fallback.
_DIPLOMACY_ALLIED_INTRO = (
    "My lord, the following Kings have wisely allied with thy ever-victorious majesty:"
)
_DIPLOMACY_WAR_INTRO = (
    "My lord, the following Kings are foolishly at war with thy ever-victorious majesty:"
)
_DIPLOMACY_NEUTRAL_INTRO = (
    "My lord, the following Kings are cautiously neutral with thy ever-victorious majesty:"
)
_DIPLOMACY_NONE_AT_PRESENT = "None at present"


def _diplomacy_entry(state: GameState, other_kingdom_id: int) -> str:
    king_id = _king_leader_id(state, other_kingdom_id)
    name = state.leaders[king_id].name if king_id is not None else state.kingdoms[other_kingdom_id].name
    return f"{name} (#{other_kingdom_id})"


def describe_diplomacy_report(state: GameState, kingdom_id: int) -> list[str]:
    """Assembles the "DIPLOMACY" section (Phase 218) -- Allied/At War/
    Neutral lists of every other kingdom, from this kingdom's own
    point of view.

    **The real procedure tracks a genuine 3-state relation per kingdom
    pair** (`kallst[kng,k2]`, `Write_List(allstate)` called once per
    state value) -- this project's own `GameState.allied_kingdoms`
    (a flat `set[frozenset[int]]`, `is_allied()`) only ever models a
    2-state relation (allied or not), confirmed absent for the third
    "at war" state -- no war-declaration mechanism exists anywhere in
    this project. **AT WAR therefore always renders empty** (real,
    sourced `_DIPLOMACY_NONE_AT_PRESENT`, not a guess at zero wars);
    every other kingdom not in `allied_kingdoms` is listed as NEUTRAL
    instead, since this project has no way to distinguish a genuine
    war from ordinary neutrality.

    **What this deliberately does NOT reproduce**: the real
    `Write_List`'s own optional per-entry enrichment (a known King's
    tax-base/treasury figure, gated on the *reader* currently holding
    the Emperor/Treasurer office and having met that King; an
    alignment note for Heavenly/Undead or same-alignment Kings) needs
    office-holder tracking (`IMPERIAL OFFICE REPORT`'s own still-open
    gap) and per-King alignment-visibility state this project doesn't
    model -- only the bare `<name> (#<kingdom_id>)` entry renders.

    Each entry's own King is resolved via `_king_leader_id()`
    (Phase 217); a kingdom with no `is_king`-flagged leader recorded
    falls back to its own `KingdomState.name` rather than guessing a
    King's name.
    """

    other_kingdom_ids = sorted(k for k in state.kingdoms if k != kingdom_id)
    allied_ids = [k for k in other_kingdom_ids if state.is_allied(kingdom_id, k)]
    neutral_ids = [k for k in other_kingdom_ids if not state.is_allied(kingdom_id, k)]

    lines = ["DIPLOMACY", _DIPLOMACY_ALLIED_INTRO]
    lines.extend([_diplomacy_entry(state, k) for k in allied_ids] or [_DIPLOMACY_NONE_AT_PRESENT])
    lines.append(_DIPLOMACY_WAR_INTRO)
    lines.append(_DIPLOMACY_NONE_AT_PRESENT)
    lines.append(_DIPLOMACY_NEUTRAL_INTRO)
    lines.extend([_diplomacy_entry(state, k) for k in neutral_ids] or [_DIPLOMACY_NONE_AT_PRESENT])

    return lines


# HostAK/TP/REPORTS.PAS Rep_Econ (~line 272-403) -- the real
# "FINANCES" section's own sourced, verbatim opening and Discoveries
# intro (each rejoined across its own raw WRITELN lines, same
# convention as _ARMIES_REPORT_OPENING).
_FINANCES_OPENING = (
    "O Great One, I submit for thy examination the following figures "
    "concerning the finances of our great nation:"
)
_FINANCES_DISCOVERIES_INTRO = (
    "Our Kingdom is also benefited by the following Discoveries of the Sages:"
)
_FINANCES_NONE_AT_PRESENT = "None at present"


def describe_finances_report(state: GameState, kingdom_id: int) -> list[str]:
    """Assembles the "FINANCES" section (Phase 219) -- a deliberately
    narrow slice of `REPORTS.PAS Rep_Econ`, rendering only the figures
    this project's `GameState` actually has real data for.

    **"Gold in treasury"** (`KingdomState.treasury`, `lgold[kng]`) and,
    as of Phase 225, **"Expected Revenues"** (`Tax_Base(kng)`, real
    source text confirmed verbatim at `REPORTS.PAS` line 319: `'
    Expected Revenues: ',Tax_Base(kng):3`) both render. `Tax_Base`
    itself is never *defined* in any available `.PAS` file -- still
    true, the same citation `describe_armies_report()`'s own docstring
    and `plan_dispatch.py`'s Phase 158 note already established -- but
    Phase 225's `turn/tax_base.py compute_tax_base()` supplies a
    project-original aggregation over the real per-province tax data
    Phases 222-224 recovered, closing this specific line's gap even
    though the real formula's own Pascal source is still lost.

    **"Expected Expenses" (Phase 276)**: `ACost`/`LCost` are still never
    *defined* in any available `.PAS` file (Phase 275's own audit), but
    the user supplied real generated `SE3__T*.K*` sample reports
    (2026-07-29) that let this line's own two components be verified
    directly against actual game output rather than only cited from a
    lost Pascal source -- see `turn/expenses.py compute_expected_
    expenses()`'s own docstring for the full cross-check (army
    maintenance confirmed exact across four independent samples; leader
    maintenance reuses `turn/hire_pay.py required_pay()`, confirmed
    against three of four real Heroes, with one known race-related
    mismatch documented rather than silently accepted).

    **The optional "(Including +5 Black Knights)"/"(Including +10
    Thieves Guild)" notes (Phase 277)**: render right after "Gold in
    treasury" and *before* "Expected Revenues" -- confirmed directly
    against five independent real `SE3__T*.K1` samples (not the position
    Phase 275/276's own notes assumed; that guess, based only on nearby
    Pascal line numbers rather than real generated output, is corrected
    here). One sample (`SE3__T7.K1`) shows the office-holder's own
    ADVENTURE-section narrative announcing the title with no FINANCES
    note yet; the very next turn's own sample (`SE3__T8.K1`, same
    kingdom) shows the note -- the gold bonus, and its note, start
    applying the turn *after* the title is earned, not immediately.
    Wired via `turn/office_holder.py resolve_office_holder()` against
    the newly-modeled `Office.EVIL_KING`/`Office.THIEF_PRINCE` (Phase
    277, `turn/merit_points.py evilking_merit_points()`/`thiefprince_
    merit_points()`) -- King of Pain's own note checks whether this
    kingdom's own King holds `EVIL_KING` directly; Prince of Thieves'
    own note checks whether the `THIEF_PRINCE` holder (King *or* Hero)
    belongs to this kingdom, matching `REPORTS.PAS`'s own `LKing(
    titchar[ThiefPrince]) = kng` check (the gold always credits the
    holder's own King's kingdom, even when a Hero holds the title).

    **Phase 435**: all three gold figures ("Gold in treasury"/"Expected
    Revenues"/"Expected Expenses") are now right-justified to the real
    `:3` field width, confirmed verbatim at `REPORTS.PAS` lines 314/319/
    322 (`WRITELN(playfile,'  Gold in treasury:  ',lgold[kng]:3)` and
    its two siblings) -- previously rendered unpadded.

    **Phase 268 closes the "+Invention Bonus" line and the Discoveries
    of the Sages list**, both previously confirmed-absent (no per-
    kingdom Discovery-tracking field existed anywhere in this project
    before Phase 266's `KingdomState.discoveries`). `+Invention Bonus`
    only renders when `compute_invention_bonus_percent()` is positive
    (`IF Inv_Bonus(kng) > 0`, real Pascal text quoted in `models/
    discovery.py`'s own module docstring); the Discoveries list renders
    one real report line per owned Discovery (`describe_discovery_line()`,
    sorted the real way via `sorted_kingdom_discoveries()`), falling back
    to `_FINANCES_NONE_AT_PRESENT` only when the kingdom holds none.
    """

    kingdom = state.kingdoms[kingdom_id]

    lines = [
        "FINANCES",
        _FINANCES_OPENING,
        f"Gold in treasury: {kingdom.treasury:>3}",
    ]
    evilking_holder = resolve_office_holder(state, Office.EVIL_KING)
    if evilking_holder is not None and state.leaders[evilking_holder.leader_id].kingdom_id == kingdom_id:
        lines.append("(Including +5 Black Knights)")
    thiefprince_holder = resolve_office_holder(state, Office.THIEF_PRINCE)
    if thiefprince_holder is not None and state.leaders[thiefprince_holder.leader_id].kingdom_id == kingdom_id:
        lines.append("(Including +10 Thieves Guild)")
    lines.append(f"Expected Revenues: {compute_tax_base(state, kingdom_id):>3}")
    lines.append(f"Expected Expenses: {compute_expected_expenses(state, kingdom_id):>3}")
    invention_bonus_percent = compute_invention_bonus_percent(kingdom)
    if invention_bonus_percent > 0:
        lines.append(f"+Invention Bonus: {invention_bonus_percent}%")
    lines.append(_FINANCES_DISCOVERIES_INTRO)
    if kingdom.discoveries:
        lines.extend(describe_discovery_line(d) for d in sorted_kingdom_discoveries(kingdom.discoveries))
    else:
        lines.append(_FINANCES_NONE_AT_PRESENT)
    return lines


# HostAK/TP/REPORTS.PAS Rep_Provs (~lines 404-450) -- the real "PROVINCES"
# section's own sourced, verbatim opening, rejoined across its 2 raw
# WRITELN lines (same convention as _ARMIES_REPORT_OPENING/_FINANCES_OPENING).
_PROVINCES_OPENING = (
    "O superfluous one, I have kept well a list of all provinces which have had "
    "the wisdom to submit to thy yoke.  Here, then, are the lands of thy Empire:"
)

_PROVINCES_NONE_AT_PRESENT = "None at present"

# REPORTS.PAS Rep_Provs, lines 436-439, verbatim (both raw WRITELN
# strings, not rejoined -- these are two separate output lines, not one
# wrapped sentence like `_PROVINCES_OPENING` above). Phase 288 wires
# these in for real, alongside the fixed-width row format and the tax-
# tier sort order they head -- see `describe_provinces_report()`'s own
# docstring.
_PROVINCES_COLUMN_CAPTION = "                                                    Recruiting Types:"
_PROVINCES_COLUMN_HEADER = "Province            Tax   Race   Terrain  Expl%     Type 1     Type 2"

# REPORTS.PAS line 426-427: `Min(11,ptax[px,py] + 8*ord((px = bornx[kng])
# and (py = borny[kng])))` -- see this module's own Phase 288 docstring
# addendum for the full derivation.
_PROVINCE_TAX_TIER_HOME_BONUS = 8
_PROVINCE_TAX_TIER_MAX = 11


def _province_tax_tier(province: ProvinceState, coord: HexCoord, kingdom: KingdomState) -> int:
    """REPORTS.PAS's own `Min(11,ptax + 8*is_home_province)` tier formula (Phase 288).

    `province_tax_yield()` returning `None` (no real-world-file data
    bridged for this province) falls back to 0 for this sort-order
    computation only -- a presentation placement, not an assertion that
    the province's real tax is zero (the same "no data isn't a true
    zero" stance this module already takes for the Tax *column* itself,
    which still omits the figure entirely when unknown).
    """

    tax_yield = province_tax_yield(province) or 0
    home_bonus = _PROVINCE_TAX_TIER_HOME_BONUS if coord == kingdom.home_province else 0
    return min(_PROVINCE_TAX_TIER_MAX, tax_yield + home_bonus)


def describe_provinces_report(state: GameState, kingdom_id: int) -> list[str]:
    """Assembles the "PROVINCES" section (Phase 220) -- a deliberately
    narrower slice of `REPORTS.PAS Rep_Provs`, the same "narrower than
    the real procedure, documented why" precedent `describe_armies_report()`
    and `describe_adventure_report()` already established.

    **Sourced and rendered**: every province this kingdom owns
    (`ProvinceState.owner_kingdom_id == kingdom_id`), one fixed-width
    row each -- name (or a `(x, y)` coordinate fallback, the same
    convention `describe_armies_report()` already uses for an unnamed
    province), race (`RACE_NAME`), terrain (`TERRAIN_NAME`, via
    `effective_terrain()` so a cast Part Sea/Flood is reflected -- not
    `illusory_terrain`, which only deceives *outside* observers and must
    never leak into a kingdom's own report of its own land), and percent
    explored (`explored_percent`; the real `pex[px,py]` is a single
    per-province value, not per-kingdom, matching this project's
    already-modeled scalar field rather than `explored_percent_by_kingdom`).

    **Tax and Recruiting Types, Phase 278**: the real table's **Tax**
    column (`ptax[px,py]`, via `turn/tax_base.py province_tax_yield()`,
    the same scar-terrain/Bless/Earthquake-adjusted figure `compute_tax_
    base()` already sums) and **Recruiting Types** columns (`Mod_PAT(px,
    py,0)`/`Mod_PAT(px,py,1)`, via `ProvinceState.recruit_type_1`/
    `recruit_type_2` and `ARMY_TYPE_DESIGNATION`) render whenever known.
    Phase 220/275 called both "confirmed absent" -- true only of a
    Pascal *formula* (neither `ptax` nor `Mod_PAT` is ever computed
    anywhere in the surviving archive, still the case). What Phase 275's
    audit didn't re-check: `parser/gw_world.py`/`gw_world_bridge.py`
    (Phase 222-224, 278) already recover both real values straight from a
    `GW3`-family world file, the same "world-gen-only data, sourced from
    a real snapshot rather than a formula" category `name` closed in
    Phase 150 -- see that module's own docstring for the full,
    zero-conflict decode evidence. Both render blank (the fixed-width
    field's own empty string, not a fabricated zero) for a province
    whose `GameState` was never bridged from a real world file (`tax is
    None`/`recruit_type_1 is None`) -- no data isn't a true zero, the
    same stance `turn/tax_base.py` itself already takes. `recruit_type_2`
    prints only when known and not the real "no second recruit type"
    case -- both look identical from a caller's perspective (nothing to
    show), so this composer doesn't need to distinguish them (see
    `ProvinceState.recruit_type_2`'s own docstring).

    **Type 2 terrain "(Sea)" parenthetical (`pt2`), Phase 282/283**: still
    genuinely confirmed absent from every surviving `.PAS` file (Phase
    275's own audit, re-confirmed, not just repeated) -- a *different*
    kind of closure from `ptax`/`Mod_PAT`/`Qual_Modfr`/`Pay` before it
    (Phase 276/278/279/280), none of which is "formula lost, data
    sourced elsewhere" here: no real Pascal formula AND no real-file
    data source exist for `pt2` at all. What renders now
    (`ProvinceState.is_island`, appended as `" (Sea)"` right after the
    terrain name -- Type 1, the land terrain, is `terrain_name` itself;
    Type 2, `is_island`, renders as the literal string `"Sea"`, per the
    user's own real-report example, `"Jungle (Sea)"`, 2026-07-29,
    correcting this composer's own first-draft `" (Island)"` wording) is
    **project-original**, implemented per the user's own explicit domain
    knowledge rather than recovered from any source -- an optional Super
    AK variant rule (games up to 24 players): a province that's half
    Sea, half its own land terrain, where armies fight at a blended
    half-land/half-Sea strength (`turn/strength.py compute_effective_
    strength()`'s own `is_island` parameter; overflight-air units --
    Dragons, Eagles -- are exempt, the user's own words). Set at world-
    creation time via the new `turn/island_provinces.py apply_island_
    provinces()` (an exact-count picker, not a percentage), never
    inferred at runtime.

    **The real table's own "Type 1"/"Type 2" column pair is a different,
    unrelated pair of columns** -- the user's own real-report header,
    `"Province Tax Race Terrain Expl% Type 1 Type 2"`, confirms these
    hold the Recruiting Types (`Mod_PAT`, e.g. `"Legion"`/`"Fleet"`),
    already rendered here in their own dedicated columns (Phase 278) --
    not terrain at all. The Island-province Type 1/Type 2 terrain split
    lives entirely inside the single `Terrain` column instead
    (`"Jungle (Sea)"`), matching this composer's own one-row-per-
    province shape.

    **Fixed-width columns and tax-tier grouping, Phase 288**: both were
    previously left as documented "presentation choice, not a missing
    data gap" omissions, the same way every other section composer in
    this module treats fixed-width formatting -- closed now, directly
    from `REPORTS.PAS Rep_Provs` (~lines 425-445), quoted here in full:
    ```
    FOR tt:= 11 DOWNTO 0 DO FOR px:= left TO right DO FOR py:= top TO bottom DO
        IF powner[px,py] = kng THEN IF Min(11,ptax[px,py] +
            8*ord((px = bornx[kng]) and (py = borny[kng]))) = tt THEN BEGIN
          ...
          WRITELN(playfile,pname^[px,py],'':20-Length(pname^[px,py]),ptax[px,py]:3,
            rname[Mod_PRace(px,py)]:8,tername[pterr[px,py]]:9,pex[px,py]:6,'%',
            atdesig[Mod_PAT(px,py,0)]:11,atdesig[Mod_PAT(px,py,1)]:11);
    ```
    Reading this directly (rather than the earlier docstring's own
    paraphrase, which turns out to have overstated it) settles two
    things this project previously had wrong or unconfirmed:
    - **No per-tier subheading exists at all.** The column header
      (`_PROVINCES_COLUMN_CAPTION`/`_PROVINCES_COLUMN_HEADER`) prints
      exactly once, guarded by a `none`-style "have we printed anything
      yet" flag that's shared across the *entire* province list, not
      reset per tier. "Grouped by descending tax tier" means only that
      the `tt` loop (11 downto 0) determines row *order* -- it produces
      no visible boundary text between tiers. This corrects this
      module's own earlier "subheadings per tier" description, which
      was written before this project had direct access to
      `REPORTS.PAS` and turns out to have been an overstatement.
    - **The tier itself** is `min(11, tax + 8)` *only for whichever
      province is this kingdom's own home province* (`px = bornx[kng]
      and py = borny[kng]`) -- every other owned province's tier is
      just its own `tax` (still capped at 11). `_province_tax_tier()`
      implements this exactly; sort key is `(-tier, x, y)`, i.e.
      descending tier (matching `tt` counting down from 11), then
      ascending coordinate within a tier (matching the `px`/`py` loops'
      own ascending `left TO right`/`top TO bottom` order) -- the same
      role `describe_armies_report()`'s own coordinate sort played
      before this phase, now demoted to a tie-breaker instead of the
      primary key.

    Fixed-width fields follow the Pascal `:N` widths literally: name
    left-justified in 20, Tax/Race/Terrain/Expl%/Type-1/Type-2 right-
    justified in 3/8/9/6/11/11 respectively (Python's own `str.ljust`/
    `str.rjust` never truncate a longer value either, the same "overflow
    past the field width, don't cut it" behavior Pascal's `:N` already
    has -- relevant here since an Island's own `"Jungle (Sea)"` terrain
    string is wider than its 9-char field). A missing Tax/Type-1/Type-2
    value renders as blank spaces filling that same field width, not a
    fabricated figure -- the column header/caption above them are
    literal, hand-aligned Pascal strings in their own right and aren't
    derived from these same field-width computations, so the two need
    not (and in the real source don't) align to the same character
    columns.
    """

    kingdom = state.kingdoms[kingdom_id]
    lines = ["PROVINCES", _PROVINCES_OPENING]

    owned = [
        (coord, province)
        for coord, province in state.provinces.items()
        if province.owner_kingdom_id == kingdom_id
    ]
    if not owned:
        lines.append(_PROVINCES_NONE_AT_PRESENT)
        return lines

    owned.sort(key=lambda entry: (-_province_tax_tier(entry[1], entry[0], kingdom), entry[0].x, entry[0].y))

    lines.append(_PROVINCES_COLUMN_CAPTION)
    lines.append(_PROVINCES_COLUMN_HEADER)

    for coord, province in owned:
        province_label = province.name if province.name else f"({coord.x}, {coord.y})"
        race_name = RACE_NAME[province.race]
        terrain_name = TERRAIN_NAME[province.effective_terrain()]
        if province.is_island:
            terrain_name += " (Sea)"

        tax_yield = province_tax_yield(province)
        tax_field = f"{tax_yield:>3}" if tax_yield is not None else " " * 3

        type1_name = ARMY_TYPE_DESIGNATION[province.recruit_type_1] if province.recruit_type_1 is not None else ""
        type2_name = ARMY_TYPE_DESIGNATION[province.recruit_type_2] if province.recruit_type_2 is not None else ""

        lines.append(
            f"{province_label:<20}{tax_field}{race_name:>8}{terrain_name:>9}"
            f"{province.explored_percent:>6}%{type1_name:>11}{type2_name:>11}"
        )

    return lines


# The real "royal scribe" intro (Phase 562), verbatim, confirmed
# byte-for-byte identical across every real sample checked this phase
# (`SE3__T1.K2`/`T4.K6`/`T5.K2` and others). Unlike every other section
# here, the real map has no standalone header of its own -- it's a
# direct continuation of PROVINCES, introduced by this one sentence
# after a blank-line gap, the same "no header" shape `ALIGNMENT
# REDUCTION`'s own real-vs-project-original distinction doesn't apply
# to here since this section genuinely has none in the source.
_MAP_REPORT_INTRO = "Sire, our royal scribe has drawn up a map of all neighboring lands:"

# REPORTS.PAS's own map key + caption, verbatim, byte-for-byte identical
# across every real sample checked this phase.
_MAP_KEY_LINE = "Key:   _ Plains   + Forest   & Jungle   ^ Mountain   . Desert     Sea"
_MAP_CAPTION_LINE_1 = "    In each province, the name and I.D. number of the province"
_MAP_CAPTION_LINE_2 = "  are listed above the ruler I.D and name."

# Phase 624: the real intro for every map page after the first, verbatim
# from real samples (e.g. `SE3__T5.K1`/`SE3__T10.K1`) -- see `report/
# ascii_map.py`'s own module docstring Phase 624 addendum for the full
# "far side of the world" pagination trigger this feeds.
_MAP_FAR_SIDE_INTRO = "We also drew up this map of lands on the far side of the world:"


def describe_map_report(state: GameState, kingdom_id: int) -> list[str]:
    """The real ASCII map (Phase 562) -- see `report/ascii_map.py`'s own
    module docstring for the full, sourced field-by-field derivation and
    exactly which real cases this phase does and doesn't reproduce.

    Returns an empty list when there are no provinces to render at all
    -- matching every other section composer's own "nothing to say,
    omit the section" convention, even though the real map has no
    header of its own for `compose_letter_report()` to conditionally
    skip the way it does for headered sections.

    Phase 577: `map_region_label()` -- "Ice cap" plus its own 78-dash
    rule, both real, sourced lines -- is inserted right after each
    page's own intro sentence's blank-line gap, before that page's own
    grid, exactly matching every real sample that shows it; omitted
    entirely (no gap left behind) for a page whose own topmost row
    doesn't reach the world's own northern edge.

    Phase 624: when the Kingdom's own known provinces span more columns
    than one page can print, the report splits into a "far side of the
    world" second (and further) page -- `report/ascii_map.py paginate_
    known_columns()`'s own home-anchored windowing decides which
    columns land on which page; see that function's own docstring and
    the module's Phase 624 addendum for the full sourcing.

    Phase 627: which of the 6 real layout tiers to use is now chosen by
    `select_layout_tier()` -- a labeled, 82%-accurate best-effort
    approximation, not a solved formula (see that function's own
    docstring for why the remaining gap needs real per-turn history
    this project can't recover from report snapshots). Every page of a
    given report uses the same chosen tier, matching every real sample
    (a report's own far-side page never switches tiers mid-report).

    Phase 628: only provinces this Kingdom actually knows about
    (`ProvinceState.known_to_kingdom()`, Phase 623) are rendered --
    previously every province in `state.provinces` rendered
    unconditionally, a real gap flagged since Phase 624 (see `report/
    ascii_map.py`'s own Phase 628 addendum). This filtered set also
    drives tier selection and pagination, not just the grid itself.
    """

    visible_provinces = {coord for coord, province in state.provinces.items() if province.known_to_kingdom(kingdom_id)}
    known_columns = {coord.x for coord in visible_provinces}
    if not known_columns:
        return []

    kingdom = state.kingdoms.get(kingdom_id)
    home_x = kingdom.home_province.x if kingdom is not None else min(known_columns)

    chosen_stride = select_layout_tier(known_columns, home_x)
    renderer = next(render for stride, render in LAYOUT_TIERS if stride == chosen_stride)
    pages = paginate_known_columns(known_columns, home_x, max_columns_per_page(chosen_stride))

    lines: list[str] = ["", "", f"  {_MAP_REPORT_INTRO} ", ""]
    for page_index, page_columns in enumerate(pages):
        columns = set(page_columns)
        grid_lines = renderer(state, kingdom_id, columns=columns, visible_provinces=visible_provinces)
        region_label = map_region_label(state, columns=columns, visible_provinces=visible_provinces)
        region_lines = [region_label, MAP_REGION_LABEL_RULE] if region_label else []

        if page_index > 0:
            lines.extend([f"  {_MAP_FAR_SIDE_INTRO} ", ""])
        lines.extend(region_lines)
        lines.extend(grid_lines)

    lines.extend(
        [
            "",
            _MAP_KEY_LINE,
            _MAP_CAPTION_LINE_1,
            _MAP_CAPTION_LINE_2,
        ]
    )
    return lines


# HostAK/TP/REPORTS.PAS Rep_Leaders (~lines 658-855) -- the real
# "CHARACTERS" section's own sourced, verbatim opening, rejoined across
# its 3 raw WRITELN lines (same convention as _ARMIES_REPORT_OPENING).
# Quoted here even though this composer doesn't render everything the
# opening itself describes ("shows pay and abilities... move precedence
# and aptitude") -- the same "quote the real opening verbatim regardless
# of what actually renders below" precedent _FINANCES_OPENING already
# established.
_CHARACTERS_OPENING = (
    "My Lord, Great indeed are the leaders of our proud kingdom.  Though thee "
    "knows them well, I list them here for thy consideration (the first line "
    "shows pay and abilities; line 2 shows move precedence and aptitude.)"
)

_CHARACTERS_NONE_AT_PRESENT = "None at present"

# REPORTS.PAS Rep_Leaders (~lines 818-824) -- the real column-caption
# block, verbatim (Phase 432). Quoted even though the middle line's own
# "Modified... Combat/Magical/Other" grouping only really matters once
# printer underline (`UL`/`NUL`, a terminal escape code with no plain-
# text equivalent) highlighted the column header beneath it -- kept for
# fidelity regardless.
_CHARACTERS_CAPTION_LINE_1 = "                                         Pay Modified Skills/Aptitudes:"
_CHARACTERS_CAPTION_LINE_2 = "             Province                     /  Combat     Magical    Other"
_CHARACTERS_COLUMN_HEADER = "Character      Loc Align  Temp M/F  Race Ini TaMaNaArMe WhNeElPsIl DrThExSpSa"

# Unsourced, documented placeholder (Phase 432) -- real `lalign`/`ltemper`
# are always populated; this project's own "None = not recorded"
# convention needs *some* short abbreviated string to fill the real
# 6-wide column when a leader has neither, and there's no real Pascal
# text for "not recorded" to quote.
_CHARACTERS_UNKNOWN_ABBREVIATION = "Unkn"


def _ability_value_row(values: list[int], *, tactical_widens: bool) -> str:
    """Renders 15 per-`Ability` values (enum order) as the real report's
    own fixed-width row -- each value right-justified width 2, except
    the first ability of every group-of-5 (indices 0, 5, 10, matching
    the header's own "TaMaNaArMe WhNeElPsIl DrThExSpSa" group spacing)
    gets width 3 instead.

    **Now only used for the aptitude row** (`Desc_Apt`, `REPORTS.PAS`
    ~line 525: `aptitude^[tro,sk]:2+ord((sk <> Tactical) and (ord(sk)
    MOD 5 = 0))`, `tactical_widens=False` -- its own group rule
    explicitly excludes Tactical, unlike the skill row's own rule; its
    leading column is a different value entirely, `Total_Skill`+March
    bonus occupying the "Ini" position, so Tactical's own aptitude value
    doesn't need the extra separating space the skill row's Tactical
    does). **The skill row moved to its own `_skill_row_with_item_ticks()`
    (Phase 437)** once the real magic-item-ownership tick marks
    (`space_sub`) needed weaving into its own per-ability width
    calculation -- this function's own flat `values: list[int]` shape
    can't carry that extra state, so it stayed simple rather than
    growing a tick-mark parameter only the skill row would ever use.
    """

    parts = []
    for index, value in enumerate(values):
        widen = index % 5 == 0 and (tactical_widens or index != 0)
        parts.append(f"{value:>{3 if widen else 2}}")
    return "".join(parts)


def _total_skill(state: GameState, leader: LeaderState) -> int:
    """`Total_Skill(leader)` -- the sum of `effective_skill_level()`
    ("M_Skill", this project's already-established real equivalent,
    `turn/discovery_effects.py`, `turn/merit_points.py
    _skill_level_sum()`'s own precedent) across all 15 `Ability`
    members. Feeds `describe_characters_report()`'s own aptitude-row
    leading value (`Total_Skill(leader) + M_Skill(leader,
    ForcedMarch)*2`, `Desc_Apt`, `REPORTS.PAS` ~line 525) -- the user's
    own explicit "Implementa Total_Skill per intero" choice, not a
    placeholder.
    """

    return sum(effective_skill_level(state, leader, ability) for ability in Ability)


def _discovery_skill_modifier_row(kingdom: KingdomState) -> str:
    """CHARACTERS' own Discovery-based skill-modifier row (`sk_mod`,
    `REPORTS.PAS` ~lines 823-834), printed once, right above the first
    leader's own skill row (Phase 625). Marks each of the 5 Combat
    abilities (Tactical..Melee) and 5 "Other" abilities (Druid..Sage)
    with `'^ '` if this Kingdom knows exactly one of that ability's own
    2 linked Discoveries, `'^^'` if it knows both, `'  '` if neither --
    the 5 Magical abilities (White..Illusion) never get a marker at all
    (`sk_mod:= 0` unconditionally in the source for that group).

    `discovery(2*sk)`/`discovery(2*sk+1)` for the Combat group and
    `discovery(2*sk-10)`/`discovery(2*sk-9)` for the Other group --
    `models/discovery.py Discovery`'s own enum is already positional
    with the Pascal source's own `discovery` ordinals (module
    docstring), so these translate directly to `Discovery(2 * ability.
    value)` etc., no remapping needed. Verified against `Desktop/
    PROGRAMMA AK/SE3__T5.K1` line 811's own real single-`'^'` marker
    (column 53, i.e. relative offset 8 within this row's own 45-char-
    prefixed marker sequence -- Melee's own first marker character,
    `sk_mod=1`) -- confirmed byte-for-byte, not just formula-shape.

    The 45-char leading blank (`REPORTS.PAS`'s own literal `WRITE`
    string immediately before the `FOR sk` loop, counted directly from
    source) is one character wider than the per-leader row's own
    44-char prefix (`{name:<14}{loc:>4}{align:>6}{temp:>6}   {race:>7}
    {pay:>3} `) -- a real, confirmed quirk of the original report (the
    two rows don't perfectly column-align even in a genuine sample),
    not a bug to "fix" here.
    """

    parts = [" " * 45]
    for ability in Ability:
        if ability.value <= Ability.MELEE.value:
            d1, d2 = Discovery(2 * ability.value), Discovery(2 * ability.value + 1)
        elif ability.value >= Ability.DRUID.value:
            d1, d2 = Discovery(2 * ability.value - 10), Discovery(2 * ability.value - 9)
        else:
            d1 = d2 = None
        sk_mod = 0 if d1 is None else int(d1 in kingdom.discoveries) + int(d2 in kingdom.discoveries)
        parts.append("  " if sk_mod == 0 else "^ " if sk_mod == 1 else "^^")
        if ability in (Ability.MELEE, Ability.ILLUSION):
            parts.append(" ")
    return "".join(parts)


def _skill_row_with_item_ticks(state: GameState, leader: LeaderState) -> str:
    """CHARACTERS line 1's own skill row, interleaved with the real
    magic-item-ownership tick marks (`REPORTS.PAS` ~lines 863-870, Phase
    437 -- see `describe_characters_report()`'s own docstring for the
    full derivation, including why `NT_Owned`'s own missing definition
    doesn't block this: its observable return value at this call site is
    just "how many of this one item type does this leader own", which
    `state.items_held_by()` already answers directly).

    Width per ability: 2, plus 1 if this is the first ability of a
    group-of-5 (`ord(sk) MOD 5 = 0` -- matches `_ability_value_row(...,
    tactical_widens=True)`'s own rule), minus 1 if the *previous*
    ability's own tick mark was printed (`space_sub`, clamped to at most
    1 regardless of how many duplicate items are owned -- a `"` costs
    the same one character as a `'`).
    """

    parts = []
    previous_owned_count = 0
    for index, ability in enumerate(Ability):
        widen = index % 5 == 0
        width = 2 - min(previous_owned_count, 1) + (1 if widen else 0)
        value = effective_skill_level(state, leader, ability)
        parts.append(f"{value:>{width}}")

        ability_item = Treasure(ability.value)
        owned_count = sum(1 for item in state.items_held_by(leader.leader_id) if item.treasure == ability_item)
        if owned_count == 1:
            parts.append("'")
        elif owned_count >= 2:
            parts.append('"')
        previous_owned_count = owned_count
    return "".join(parts)


def _best_ability(state: GameState, leader: LeaderState) -> tuple[Ability, int]:
    """``Best_Ab(ldr,ab,lev)`` (Phase 638): `ldr`'s highest-skilled
    `Ability` and its level, feeding `_leader_ability_description()`
    below. `Best_Ab`'s own body doesn't survive in any of the 13
    available `.PAS` files -- only its call site (`RUMORS.PAS Get_
    AbDesc`, line 486) does. The *concept* ("this leader's best
    ability") is trivial; the exact tie-break when two abilities are
    level-tied is genuinely unsourced. This picks the first `Ability`
    (declaration order: Tactical, March, Naval, Archery, Melee, White,
    Necromancy, Elemental, Psychic, Illusionist, Druid, Thief, Explorer,
    Spy, Sage) reaching the max -- `max(..., key=...)` keeps the
    first-seen maximum on a tie for free. Documented as a reasonable,
    unproven choice, the same class of gap Phase 627's own tier-
    selection tie-break already accepted. A `skills=None` leader reads
    0 for every ability (`effective_skill_level()`'s own established
    convention) and lands on `(Ability.TACTICAL, 0)`.
    """

    best = max(Ability, key=lambda ability: effective_skill_level(state, leader, ability))
    return best, effective_skill_level(state, leader, best)


_ABILITY_LEVEL_PHRASE = {
    0: "noted for ",
    1: "well known for ",
    2: "famous for ",
    3: "renowned for ",
    4: "world-famous for ",
    5: "revered for ",
    6: "worshipped for ",
}


def _leader_ability_description(state: GameState, leader: LeaderState) -> str:
    """``Get_AbDesc`` (`RUMORS.PAS` lines 481-507, Phase 638): "(a RACE
    LEVEL_PHRASE for ABILITY_NOUN)", e.g. "(a Human famous for
    Archery)". `anoun` (the ability-noun table `Get_AbDesc` reads) is
    already ported verbatim as `models/enums.py ABILITY_NAME` --
    confirmed via `Ability.MELEE: "Meleeing"`, an exact match -- no new
    table needed. Race fallback mirrors Phase 637's own `describe_
    characters_report()` fix: a `Desc_Stranger` target is exactly the
    kind of non-owned leader with possibly no explicit `race` that fix
    was written for.
    """

    ability, level = _best_ability(state, leader)
    phrase = _ABILITY_LEVEL_PHRASE[min(level, 6)]
    race = leader.race if leader.race is not None else state.kingdoms[leader.kingdom_id].race
    return f"(a {RACE_NAME[race]} {phrase}{ABILITY_NAME[ability]})"


def _king_of_kingdom(state: GameState, kingdom_id: int) -> LeaderState | None:
    return next((leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king), None)


def _stranger_descriptor(state: GameState, target: LeaderState) -> str:
    """The "as" descriptor string (`REPORTS.PAS Desc_Stranger`, Phase
    638), capped at 26 characters like the real `Delete(as,27,99)`:
    a dead leader shows "buried in {province}"; a kingdomless leader
    shows "a wandering Hero"; a King shows "a King character";
    otherwise "{their King's name}'s Hero". Only the real procedure's
    English branch is modeled (the `Company = Roland` French variant
    renders identical text either way -- every other composer in this
    project already only renders the English branch).
    """

    if target.leader_id in state.dead_leaders:
        province = state.provinces.get(target.location)
        place = province.name if province is not None and province.name else province_code(target.location)
        descriptor = f": buried in {place}"
    elif target.kingdom_id is None:
        descriptor = ": a wandering Hero"
    elif target.is_king:
        descriptor = ": a King character"
    else:
        king = _king_of_kingdom(state, target.kingdom_id)
        descriptor = f": {king.name}'s Hero" if king is not None else ": a Hero"
    return descriptor[:26]


def _tell_align(target: LeaderState, priest: LeaderState, *, board_width: int = DEFAULT_WIDTH) -> Alignment:
    """``Tell_Align`` (`REPORTS.PAS` lines 695-713, Phase 638) -- the
    "Rod of alignment sensing" pseudo-random reveal impulse 3 always
    shows, and impulse 2 shows too when the Priest is within 2 hexes of
    the target. `target.alignment` must not be `None` -- a missing-
    alignment rendering fallback belongs to the future wiring phase,
    not this pure primitive.

    ``ta := ord(lalign[ldr]) + ((lx[ldr]+ly[tcp]) MOD tdmod) Shr 1 -
    ((100+ly[ldr]-lx[tcp]) MOD tdmod) Shr 1``, clamped to
    ``[ord(Heavenly),ord(Undead)]`` -- `models/alignment.py
    ALIGNMENT_ORDINAL`/`ALIGNMENT_BY_ORDINAL` (Phase 162) already give
    the real Pascal `outlook` ordinal sequence this needs (`Heavenly`=0
    is `Alignment.DIVINE`, `Undead`=7). `tdmod := (LDist(tcp,ldr)+1)
    Shl ord(ldr >= nkings)` -- `ord(ldr >= nkings)` is 0 for a King, 1
    for a Hero, translated here as `0 if target.is_king else 1`.
    """

    assert target.alignment is not None
    td = hex_distance_wrapped(priest.location, target.location, board_width)
    tdmod = (td + 1) << (0 if target.is_king else 1)
    tx, ty = target.location.x, target.location.y
    px, py = priest.location.x, priest.location.y
    ta = ALIGNMENT_ORDINAL[target.alignment] + ((tx + py) % tdmod) // 2 - ((100 + ty - px) % tdmod) // 2
    ta = max(ALIGNMENT_ORDINAL[Alignment.DIVINE], min(ALIGNMENT_ORDINAL[Alignment.UNDEAD], ta))
    return ALIGNMENT_BY_ORDINAL[ta]


def _was_clairved(state: GameState, target_leader_id: int, kingdom_id: int) -> bool:
    """``Was_Clairved`` (`REPORTS.PAS Rep_Leaders`, Phase 637): does any
    of `kingdom_id`'s own leaders currently hold an Enhanced-
    Clairvoyance-backed watch on `target_leader_id`? Mirrors the real
    ``FOR l2 ... IF LKing(l2)=kng THEN IF Has_SA(l2,Expand_Clair) THEN
    IF clobj=ldr THEN`` loop exactly, reading `LeaderState.clairvoyance_
    cast_target` (the caster's side, written by every successful
    Clairvoyance cast -- `turn/cast_execution.py _execute_clairvoyance()`)
    gated on `AdvancedAbility.ENHANCED_CLAIRVOYANCE` here rather than at
    write time, matching how the real write (`lspec`) and the real
    ability check (`Has_SA`) are two separate steps.
    """

    return any(
        leader.kingdom_id == kingdom_id
        and leader.clairvoyance_cast_target == target_leader_id
        and AdvancedAbility.ENHANCED_CLAIRVOYANCE in leader.advanced_abilities
        for leader in state.leaders.values()
    )


def describe_characters_report(state: GameState, kingdom_id: int) -> list[str]:
    """Assembles the "CHARACTERS" section (Phase 221) -- a deliberately
    much narrower slice of `REPORTS.PAS Rep_Leaders`, one of the largest
    procedures in the available Pascal archive (`compose_letter_report()`'s
    own docstring already flagged it as such), the same "narrower than
    the real procedure, documented why" precedent every other section
    composer in this module already established.

    **The real procedure's "impulse 1" pass is modeled in full**
    (Phase 637): a kingdom's own leaders (`LKing(ldr) = kng`, i.e.
    `LeaderState.kingdom_id == kingdom_id` here) *plus* any other
    leader successfully targeted by an Enhanced-Clairvoyance-capable
    cast from one of this kingdom's own leaders (`Was_Clairved`,
    `REPORTS.PAS Rep_Leaders` line 682 -- `_was_clairved()` below,
    driven by `LeaderState.clairvoyance_cast_target`/`AdvancedAbility.
    ENHANCED_CLAIRVOYANCE`). Both cases render through the identical
    full-row table -- `Was_Clairved` targets never need the separate
    `Desc_Stranger` prose format impulse 2/3 use, since the real
    `Dispable`/rendering `CASE` only ever routes a leader to
    `Desc_Stranger` when `impulse <> 1`.

    **Impulse 2/3 remain unmodeled**: "impulse 2" (wandering Heroes/
    other Kings' leaders this kingdom knows the location of via
    `Known_Loc`) and "impulse 3" (leaders a Priest-office-holding King
    can locate) both render through `Desc_Stranger`, an entirely
    different prose format -- not attempted here. See
    [[project_characters_impulse23_phase636]] for the full status:
    `Known_Loc`/`Ldr_Near` primitives exist (Phase 636,
    `turn/leader_visibility.py`) but aren't wired in (`orig_turn`'s
    real ak_engine mapping is still unconfirmed), and `Desc_Stranger`
    itself is entirely unbuilt. (**Phase 636 correction, kept for
    the record**: an earlier version of this docstring also named "the
    Priest office itself" as a blocker here -- false even when written,
    `turn/office_holder.py Office.PRIEST` has been a fully live,
    resolvable office since well before Phase 432; see
    [[feedback_stale_known_gap_claims]].)

    **Phase 432 rewrites this composer to the real fixed-width table**
    (the user's own explicit "tutto il report, pixel-perfect" scope
    decision) -- the 3-line caption block (`_CHARACTERS_CAPTION_LINE_1`/
    `_2`/`_CHARACTERS_COLUMN_HEADER`, quoted verbatim from `REPORTS.PAS`
    ~lines 818-824) followed by two fixed-width numeric-column lines per
    owned leader, replacing the previous "readable prose line" style
    every earlier phase here used.

    **Line 1** (`REPORTS.PAS` ~lines 847-864): name left-justified width
    14 (`Get_HName(ldr,14,s)`); `province_code(leader.location)` right-
    justified width 4 (`Get_PN`, the real "Loc" column -- `models/map.py
    province_code()`, Phase 431); alignment abbreviation right-justified
    width 6 (`ALIGNMENT_ABBREVIATION`, `models/alignment.py`, sourced
    from `CTBOTH.PAS outab`); temper abbreviation right-justified width
    6 (`TEMPER_ABBREVIATION`, `models/temper.py`, sourced from `CTBOTH.
    PAS tempab`); `Sex.value` (`M`/`F`) right-justified width 3 (**Phase
    635 correction**: this composer's own earlier claim that "no
    `Gender()` concept or field exists anywhere in this project" was
    stale even when written -- `models/sex.py Sex`/`LeaderState.sex`
    have existed since Phase 260, this composer's own `Sex` import at
    the top of this module already being used for an unrelated NEW_SEX
    power message. `LeaderState.sex` currently has exactly one real
    writer, `turn/succession.py create_king()` (a Royal Heir's sex is
    chosen at succession, confirmed with the user, `models/sex.py`'s own
    docstring); every other leader (anyone not created via succession
    during this project's own simulated turns) reads `None` and renders
    blank here, the same "no data, don't guess" convention this column
    already used. **A second, real Gender data source exists but is
    deliberately not bridged here**: `parser/gw_world.py GWKingExtension.
    is_male` (Phase 320/380) parses a King's own real Gender byte
    straight from a `GW*` save file, but nothing in this project bridges
    `GWKingExtension` records into `GameState`/`LeaderState` at all yet
    (confirmed: grepped every caller outside `parser/gw_world_writer.py`'s
    own round-trip serializer -- none) -- building that bridge would also
    need to solve associating each extension record with the right King
    (the parser discards the name it used for detection), a real,
    separate, larger follow-up this phase doesn't attempt); race name
    right-justified width 7 (`LeaderState.race`
    if set, else the kingdom's own `KingdomState.race` -- `LeaderState.
    race`'s own docstring confirms this fallback is the real, general-
    case behavior; only a Valhalla visitor keeps an independent race);
    Pay right-justified width 3 plus one literal trailing space (`turn/
    expenses.py leader_pay()`, the same formula/exclusions FINANCES'
    own "Expected Expenses" line uses -- confirmed against `SE3__T1.K2`'s
    real CHARACTERS table, Phase 280); then the skill row (`_skill_row_
    with_item_ticks()`, Phase 437), one `effective_skill_level(state,
    leader, ability)` value per `Ability` member (this project's already-
    established "M_Skill" equivalent, discovery-bonus-inclusive, 0
    unconditionally if `LeaderState.skills` is `None` or the leader is
    comatose).

    **Magic-item-ownership tick marks (Phase 437)**: `REPORTS.PAS`'s own
    skill-row loop (~lines 863-870) interleaves a `'`/`"` marker after
    each ability's number whenever this leader owns an item that boosts
    that specific ability -- `tr:= treasure(ord(sk)+ord(hla))` (`hla` is
    Treasure ordinal 0, so `tr` is exactly `models/treasure.py
    TREASURE_ABILITY_ITEM`'s own reverse mapping, `Treasure(ability.
    value)`) then `space_sub:= NT_Owned(ldr,tr,tr,trdex)`. `NT_Owned`
    itself has no surviving definition in the available Pascal archive
    (confirmed absent -- searched every `.PAS` file in the source zip,
    not just `REPORTS.PAS`), but its *observable* return value at this
    call site is fully derivable without it: called with the same
    treasure type as both range bounds, it can only be counting how many
    items of that one type this leader owns -- exactly what `state.
    items_held_by(leader.leader_id)` already answers directly, the same
    "formula lost, inputs sourced" category `turn/army_quality.py
    compute_army_modified_quality()` already closed for `Qual_Modfr`.
    Real formatting: `'` when exactly one is owned, `"` when two or
    more; the tick mark then eats one character off the *next* ability's
    own number field width (`M_Skill(ldr,sk):2 -space_sub +...`, clamped
    so a `"` never costs more than the `'` case does) so the row's total
    width stays constant regardless of how many items a leader holds.

    A leader with no recorded Alignment/Temperament renders
    `_CHARACTERS_UNKNOWN_ABBREVIATION` ("Unkn") for that field -- a
    documented, unsourced placeholder for genuinely missing data, not a
    guess at a real value (the real Pascal `lalign`/`ltemper` arrays are
    always populated; this project's own "None = not recorded"
    convention, `LeaderState.alignment`/`.temper`'s own docstrings,
    allows a gap the real engine never has).

    **Line 2 -- the aptitude row** (`Desc_Apt`, nested inside `List_Treas`,
    `REPORTS.PAS` ~lines 511-526, called unconditionally for every owned
    leader from `Rep_Leaders` line 876 -- re-derived this session after
    an earlier research pass wrongly concluded no such line existed at
    all in the real procedure, then was corrected by re-checking directly
    against `REPORTS.PAS` once the real sample reports contradicted it):
    the leading value, occupying the same column position as line 1's
    Pay/"Ini", is **`Total_Skill(leader) + M_Skill(leader,
    ForcedMarch)*2`** (`_total_skill()` below + `effective_skill_level(
    state, leader, Ability.MARCH) * 2`) -- a derived score, *not* a
    second Pay value, per the user's own explicit confirmation ("Implementa
    Total_Skill per intero") after this exact ambiguity was raised.
    Right-justified width 2, then two literal spaces (`WRITE(playfile,
    ...:2,'  ')`), then one raw `aptitude^[tro,sk]` value per `Ability`
    member via `_ability_value_row(..., tactical_widens=False)` -- the
    *raw* stored aptitude (`SkillTable.pair_for_ability(ability)[1]`, no
    discovery-bonus wrapper, unlike the skill row), and a **different**
    group-width rule than line 1's: only White(5)/Druid(10) get the wide
    treatment, Tactical(0) does not (`aptitude^[tro,sk]:2+ord((sk <>
    Tactical) and (ord(sk) MOD 5 = 0))` -- the exclusion is explicit in
    the real source).

    **The Discovery-based skill-modifier row** (`sk_mod`'s own `^`/`^^`
    markers above each ability column, `_discovery_skill_modifier_
    row()`, Phase 625) -- this docstring previously called it confirmed
    absent "for the same reason `describe_finances_report()`'s own
    Discoveries list always renders empty: no per-kingdom Discovery-
    tracking field exists anywhere in this project," which was stale
    even at the time it was written here (Phase 432): `KingdomState.
    discoveries` has existed since Phase 266, and `describe_finances_
    report()`'s own Discoveries list has read it directly since Phase
    268 -- neither claim was re-checked before repeating it. The real
    `REPORTS.PAS` formula (`sk_mod`, `discovery(2*sk)`/`discovery(2*sk
    +1)` for Combat abilities, `discovery(2*sk-10)`/`discovery(2*sk-9)`
    for the "Other" group, always 0 for the 5 Magical abilities) is
    fully sourced and now implemented -- see that function's own
    docstring for the full derivation and the real-sample byte check.

    **What this deliberately does NOT reproduce, and why**:
    - **The per-leader treasure list** (`List_Treas(ldr,false)`'s own
      item-name interleaving, which is *where* the real `Desc_Apt` call
      itself lives) is still rendered separately (Phase 287's own
      simplified "Items: X, Y" line, kept unchanged) rather than
      reproducing the real interleaved item+aptitude row layout -- the
      project's own established "readable line, not the full real
      table" convention, kept for this one sub-piece even though the
      surrounding table itself is now pixel-perfect.
    - **Move precedence** (the real line 2's other own real-world
      content, alongside aptitude) still isn't modeled.
    """

    kingdom = state.kingdoms[kingdom_id]
    lines = [
        "CHARACTERS",
        _CHARACTERS_OPENING,
        "",
        _CHARACTERS_CAPTION_LINE_1,
        _CHARACTERS_CAPTION_LINE_2,
        _CHARACTERS_COLUMN_HEADER,
        _discovery_skill_modifier_row(kingdom),
    ]

    owned = [leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id]
    king = next((leader for leader in owned if leader.is_king), None)

    # Phase 637: Was_Clairved -- a foreign leader successfully targeted by
    # an Enhanced-Clairvoyance cast from one of this kingdom's own leaders
    # also gets the full impulse-1 row. `king` above is deliberately
    # resolved from `owned` alone, before this merge, so a Was_Clairved
    # leader who happens to be a foreign King is never mistaken for this
    # kingdom's own King by any row's `leader_pay()` call below.
    clairved = [
        leader
        for leader in state.leaders.values()
        if leader.kingdom_id != kingdom_id and _was_clairved(state, leader.leader_id, kingdom_id)
    ]
    displayed = owned + clairved
    if not displayed:
        lines.append(_CHARACTERS_NONE_AT_PRESENT)
        return lines

    displayed.sort(key=lambda leader: leader.leader_id)
    for leader in displayed:
        loc = province_code(leader.location)
        alignment_label = ALIGNMENT_ABBREVIATION[leader.alignment] if leader.alignment is not None else _CHARACTERS_UNKNOWN_ABBREVIATION
        temper_label = TEMPER_ABBREVIATION[leader.temper] if leader.temper is not None else _CHARACTERS_UNKNOWN_ABBREVIATION
        sex_label = leader.sex.value if leader.sex is not None else ""
        if leader.race is not None:
            race = leader.race
        elif leader.kingdom_id is not None:
            # Phase 637: a Was_Clairved leader with no explicit race falls
            # back to his OWN kingdom's race, not the viewer's -- the
            # viewer's own `kingdom.race` fallback below is only correct
            # for a truly kingdomless leader.
            race = state.kingdoms[leader.kingdom_id].race
        else:
            race = kingdom.race
        race_label = RACE_NAME[race]
        pay = leader_pay(state, leader, king)

        skill_row = _skill_row_with_item_ticks(state, leader)
        # Phase 555: REPORTS.PAS Get_HName (AKGEN_reverse_engineering_
        # report (5).md SS6.1, machine-verified) substitutes "Royal
        # Heir" for the stored name whenever this leader is still an
        # unfinalized Royal Heir (turn/cast_execution.py
        # is_unfinalized_royal_heir()) past the game's very first turn
        # -- ldr < nkings is implicit here, since is_royal_heir is only
        # ever set on a King's own slot (GameState.remove_leader()).
        display_name = "Royal Heir" if state.turn_number > 0 and is_unfinalized_royal_heir(leader) else leader.name
        lines.append(
            f"{display_name:<14}{loc:>4}{alignment_label:>6}{temper_label:>6}{sex_label:>3}{race_label:>7}{pay:>3} {skill_row}"
        )

        skills = leader.skills
        aptitude_values = [skills.pair_for_ability(ability)[1] if skills is not None else 0 for ability in Ability]
        aptitude_row = _ability_value_row(aptitude_values, tactical_widens=False)
        total_skill_and_march = _total_skill(state, leader) + effective_skill_level(state, leader, Ability.MARCH) * 2
        lines.append(f"{total_skill_and_march:>2}  {aptitude_row}")

        held_items = state.items_held_by(leader.leader_id)
        if held_items:
            item_names = ", ".join(TREASURE_NAME[item.treasure] for item in held_items)
            lines.append(f"Items: {item_names}")

    return lines


# HostAK/TP/REPORTS.PAS Rep_Armies (~lines 888-1091) and its own
# Expand_Write('ARMIES',kng) opening (~line 1039). See
# describe_armies_report()'s own docstring for the substantial scope
# this project deliberately excludes from Rep_Armies's real behavior.
_ARMIES_REPORT_OPENING = (
    "Excellence, thy armies have trained hard and honed their weapons to a fine "
    "edge.  Proudly they serve thy imperial majesty, and they await thy commands."
)

_ARMIES_REPORT_NONE_AT_PRESENT = "None at present"

# REPORTS.PAS Rep_Armies Doit (~lines 945-950), Hired-pass variant,
# verbatim (Phase 433): `WRITE(...,'':18-Length(s))` province field +
# `WRITE(...,'  Modified')`/`WRITE(...,'  Quality')` appended directly
# after the shared "...Normal"/"...Quality" line (real column widths
# 18/15/20/7/9/9, confirmed by slicing the joined string against each
# `WRITE(...,'':N-Length(s))`/`:N` field-width call).
_ARMIES_CAPTION_LINE_1 = "                                                              Normal  Modified"
_ARMIES_COLUMN_HEADER = "Province          Leader         Designation           Race   Quality  Quality"

# REPORTS.PAS Doit's own `Check_None`-equivalent province-column
# suppression (Phase 436): the real per-province `none`/`pac` state --
# the first army at a province gets the full province field, the second
# gets `'(#'+ps+')'` (`ELSE IF ((pac = 2) and (apres >= 2)) THEN s:=
# Concat('(#',ps,')')`, `apres>=2` always true once a second army at
# the same province exists), and every later army gets `WRITE(s,'':18-
# Length(s))` with `s:= ''` -- i.e. a fully blank 18-char field, not a
# repeated province name.
_ARMIES_BLANK_PROVINCE_COLUMN = " " * 18


def describe_armies_report(state: GameState, kingdom_id: int) -> list[str]:
    """Lists every army this kingdom currently owns, grouped by province --
    a deliberately narrower slice of ``REPORTS.PAS Rep_Armies`` (the real
    "ARMIES" section of the end-of-turn letter report).

    **Sourced, verbatim**: the "ARMIES" section header (``Expand_Write``)
    and its own two-line opening flavor text, both hardcoded directly in
    ``REPORTS.PAS`` (not a ``PROSE/*.X`` template) -- rejoined here as one
    continuous sentence, the same "flowing prose split across two raw
    ``WRITELN`` lines" shape the FINANCES/PROVINCES/STATE-OF-THE-NATION
    section openings all share.

    **What this deliberately does NOT reproduce, and why** (`Rep_Armies`
    is one of the largest procedures in the available Pascal archive,
    after `Rep_Leaders`/CHARACTERS and `List_Treas`):

    - The real procedure makes two passes -- `Hired` (armies this kingdom
      actually commands) and `Mercenary` (independent mercenaries visible
      nearby that this kingdom *could* Recruit). Only the `Hired`-pass
      concept is modeled here (armies with ``ArmyState.kingdom_id ==
      kingdom_id``); the Mercenary pass needs `Known_Merc`/`Commanded`
      eligibility state this project's `GameState` doesn't track.
    - **Skeletal-Army designation (Phase 281)**: the real table's
      ``Doit`` procedure (nested inside ``Rep_Armies`` itself,
      ``REPORTS.PAS:986-992``, the exact site ``turn/army_naming.py
      make_army_display_name()`` was already built from in Phase 236)
      swaps in a distinct compact "Skel <designation>" form
      (``ARMY_TYPE_DESIGNATION``, not the ordinary ``ARMY_TYPE_NAME``)
      whenever ``astate[an] = Zomboid``. This module's own docstring
      previously claimed ``ArmyState`` had no equivalent flag at all --
      wrong: ``ArmyState.is_skeletal`` (Phase 236) is exactly that flag,
      already set by every Skeletal_Army cast (``turn/cast_execution.py
      _execute_skeletal_army()``), just never read here. Wired directly
      (the branch logic only, not `make_army_display_name()`'s own
      ordinal-number prefix, since this composer's "province -- leader:
      designation" line never rendered a per-army ordinal to begin
      with -- a distinct, already-documented formatting choice above,
      not reopened here). Cross-checked against the same real sample
      `turn/army_naming.py`'s own docstring already cites
      (`SE3__T0.K1:135`, "108th Skel Bowmen").
    - **Phase 433 adds the real column widths** (`_ARMIES_CAPTION_LINE_1`/
      `_ARMIES_COLUMN_HEADER`, quoted verbatim from `REPORTS.PAS Doit`
      ~lines 945-950 -- province 18, leader 15, designation 20, race 7,
      quality 9, modified quality 9, cross-checked by slicing the joined
      header string against each real `WRITE(...,'':N-Length(s))`/`:N`
      field-width call). The real header itself is also lazy (`strip`
      flag): it's only ever printed before the *first* eligible army
      line, never at all if this kingdom owns no armies -- reproduced
      here via the same `if not owned: return` early-out already in
      place, so "None at present" appears with no header, unlike
      CHARACTERS' own caption block (`Rep_Leaders` prints its header
      unconditionally at the top of the procedure, before the loop -- a
      genuine structural difference between the two real procedures,
      not an inconsistency introduced here).
    - **Phase 436 adds the real per-province column suppression**
      (`Check_None`'s own `pac`/`none` state, `REPORTS.PAS` ~lines
      954-971): the *first* army at a given province gets the full
      province field; the *second* gets `"(#" + province_code() + ")"`
      (the real `apres >= 2` guard is trivially satisfied whenever a
      second army at the same province exists at all); every later army
      at that province gets a fully blank 18-char field
      (`_ARMIES_BLANK_PROVINCE_COLUMN`), not a repeated province name.
      **Still not reproduced**: the real grouping is actually keyed by
      *province+leader* (the outer loop iterates leaders first, armies
      second), so a province with multiple leaders present would, in
      the real table, interleave leader-groups rather than list every
      army in flat `army_id` order the way this composer's own
      pre-existing sort does -- since the province-column suppression
      pattern itself only depends on how many armies have been printed
      at this province so far (not on which leader they belong to), it
      reproduces correctly regardless of iteration order, but the
      real leader-grouping order itself is not attempted.

    Each army's race is resolved via `models/army_type.py
    MONSTROUS_ARMY_RACE` (the army type's fixed race for monstrous types,
    else the owning kingdom's own race) -- the same interpretation
    `plan_dispatch._dispatch_recruit`'s own
    `is_army_type_compatible_with_race` already established (Phase
    12/153's own note), not `Mod_ARace`'s own unavailable formula.

    **"Modified Quality" (Phase 279)**: the real table's second quality
    column, `Qual_Modfr`, still has no surviving Pascal declaration
    (re-confirmed, not just repeated -- see `compose_letter_report()`'s
    own Phase 275/279 audit notes) -- but every one of its five real
    modifiers turned out to already be a sourced, implemented rulebook
    mechanic elsewhere in this project, the same "formula lost, inputs
    sourced" category Phase 277/278 both closed before it. Computed via
    `turn/army_quality.py compute_army_modified_quality()` (see that
    module's own docstring for the full derivation of each of the five
    modifiers) and rendered as a second `Quality` name next to the
    normal one, matching the real table's own two-column shape.
    """

    kingdom = state.kingdoms[kingdom_id]
    lines = ["ARMIES", _ARMIES_REPORT_OPENING]

    owned = [army for army in state.armies.values() if army.kingdom_id == kingdom_id]
    if not owned:
        lines.append(_ARMIES_REPORT_NONE_AT_PRESENT)
        return lines

    lines.append(_ARMIES_CAPTION_LINE_1)
    lines.append(_ARMIES_COLUMN_HEADER)

    owned.sort(key=lambda army: (army.location.x, army.location.y, army.army_id))

    province_index = 0
    previous_coord: HexCoord | None = None
    for army in owned:
        if army.location != previous_coord:
            previous_coord = army.location
            province_index = 0

        if province_index == 0:
            province = state.provinces.get(army.location)
            if province is not None and province.name:
                province_field = f"{province.name[:18]:<18}"
            else:
                province_field = f"{f'({army.location.x}, {army.location.y})'[:18]:<18}"
        elif province_index == 1:
            province_field = f"{f'(#{province_code(army.location)})':<18}"
        else:
            province_field = _ARMIES_BLANK_PROVINCE_COLUMN
        province_index += 1

        if army.commanded_by is not None and army.commanded_by in state.leaders:
            leader_label = state.leaders[army.commanded_by].name
        else:
            leader_label = "Garrison"
        if army.is_skeletal:
            designation = f"Skel {ARMY_TYPE_DESIGNATION[army.army_type]}"
        else:
            designation = ARMY_TYPE_NAME[army.army_type]
        race = MONSTROUS_ARMY_RACE.get(army.army_type, kingdom.race)
        race_name = RACE_NAME[race]
        quality_name = QUALITY_NAME[army.quality]
        modified_quality_name = QUALITY_NAME[compute_army_modified_quality(state, army)]
        lines.append(
            f"{province_field}{leader_label[:15]:<15}{designation[:20]:<20}"
            f"{race_name:>7}{quality_name:>9}{modified_quality_name:>9}"
        )

    return lines


# HostAK/TP/REPORTS.PAS Desc_Adventure (~line 2008-2126) -- the real
# "ADVENTURE" section's own opening flavor text, rejoined across its 3
# raw WRITELN lines (same convention as _ARMIES_REPORT_OPENING above),
# and its column-header line (verbatim, trailing spaces trimmed).
_ADVENTURE_REPORT_OPENING = (
    "O Luminous One, adventure awaits thee and thy companions at every corner of "
    "the globe!  Fearsome monsters lurk in their cavernous hidden lairs by day and "
    "terrorize the populace by night.  Here are these lairs:"
)

_ADVENTURE_REPORT_COLUMN_HEADER = "Province             %Exp  Features and F#     Monster         Special"

# Reuses the same real, sourced fallback phrase _ARMIES_REPORT_NONE_AT_PRESENT
# already established (confirmed real output, e.g. the DIPLOMACY section's
# own "None at present" in a real SE3__T*.K2 file) -- Desc_Adventure's own
# empty-loop case isn't separately quoted in the available source, but this
# project's own established convention for "nothing to list" is reused here
# rather than inventing a different phrase.
_ADVENTURE_REPORT_NONE_AT_PRESENT = "None at present"

# REPORTS.PAS Desc_Adventure's own monster-name-prefix-stripping rule
# (~line 2056-2059): "Renegade "/"Giant "/"Great " are dropped from the
# monster's own display name before printing (a 4th case, truncating at
# "Elemen[tal]", is part of that same procedure's fixed-width-column
# truncation logic and isn't reproduced -- Phase 434 reproduces the real
# field widths, but not this one further truncation-and-dot-insertion
# edge case).
_ADVENTURE_MONSTER_NAME_PREFIXES = ("Renegade ", "Giant ", "Great ")

# REPORTS.PAS Desc_Adventure's own `Check_None` (~lines 2018-2029) and
# `sacked &looted` literal (~line 2068) -- Phase 434, verbatim: the
# real 16-char monster-column literal used whenever `fstate[fn] = Dead`
# instead of a monster name (`WRITE(playfile,'sacked &looted  ')` --
# already exactly 16 characters long in the source, no format
# specifier needed).
_ADVENTURE_SACKED_AND_LOOTED = "sacked &looted  "

# The real per-province column-suppression width (`WRITE(playfile,
# '':27)`, Check_None's own `ELSE` branch) -- every feature after the
# first at a given province gets 27 blank columns instead of repeating
# the province/code/%exp block. The same real `'':27` literal is reused
# for the "Special"/treasure line's own indent below (REPORTS.PAS
# ~line 2089: `WRITELN(playfile,'':27,'/Guarding unknown riches...')`)
# -- Phase 430 had used a 2-space indent there, unsourced; Phase 434
# corrects it to the real 27-space width.
_ADVENTURE_BLANK_PROVINCE_COLUMNS = " " * 27


def _adventure_monster_label(monster: Monster) -> str:
    name = MONSTER_NAMES[monster]
    for prefix in _ADVENTURE_MONSTER_NAME_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


_IMPERIAL_OFFICE_REPORT_HEADER = "IMPERIAL OFFICE REPORT"
_IMPERIAL_OFFICE_REPORT_NONE = "None at present"


def _riv_percent_display(points: int | float, rival_points: int | float) -> str:
    """Real `rivstr`: `"None"` when there's no rival at all (`ftoppts ==
    0`), otherwise `points` as a percentage of the best rival's own
    score, capped at the real `LMin(30000, ...)` ceiling. Phase 440.
    """

    if rival_points == 0:
        return "None"
    return f"{min(30000, int(100 * points / rival_points))}%"


def _office_candidate_line(state: GameState, office: Office, holder: OfficeHolder, *, prefix: str) -> str:
    """One real Rank/Riv%-annotated line for `holder` (either the row's
    own top candidate or its runner-up) -- `prefix` carries the leading
    column text (the padded office name, or a blank indent for a
    runner-up line). `Rank()`/`ftoppts` are always computed relative to
    `holder`'s own Kingdom (real `REPORTS.PAS Rank(bestldr,...)`/
    `Rank(nextldr,...)`, each deriving `lak` from their own respective
    leader, not the report's own viewing Kingdom) -- matters when `top`
    is the true global winner from a *different* Kingdom than the one
    reading this report. Phase 440.
    """

    name = state.leaders[holder.leader_id].name
    rank = leader_office_rank(state, office, holder.leader_id)
    rival_points = office_rival_best_points(state, office, state.leaders[holder.leader_id].kingdom_id)
    riv = _riv_percent_display(holder.merit_points, rival_points)
    return f"{prefix}{name} ({holder.merit_points} points, rank {rank}, {riv})"


def describe_imperial_office_report(state: GameState, kingdom_id: int) -> list[str]:
    """Assembles the "IMPERIAL OFFICE REPORT" section (Phase 230; full
    rank/percentage/runner-up columns added Phase 440) -- real, sourced
    content (`REPORTS.PAS Pray_Report`'s own per-office loop, ~line
    1580-1730) this project could never render before Phase 227/228/230
    gave it the underlying pieces (real Merit Point formulas, the real
    Emperor election result, Rank-contest resolution), and Phase 438/439
    gave it the rest (per-Kingdom ranking primitives, the real alignment
    Victory Point decay formula).

    **This report is genuinely per-Kingdom and changes shape around the
    Emperor election** -- confirmed by direct re-read of the real source
    this phase, correcting this composer's own previous claim that its
    content was "the same for every kingdom's own report" (only true
    post-election): before any Emperor is elected
    (`state.emperor_kingdom_id is None`), each Kingdom's own report shows
    only *its own* best candidate for each office (`turn/office_holder.py
    kingdom_best_candidate()`, the real ungated pre-election "Best Hope"
    scan) -- not the true global leader. After an Emperor is elected, it
    shows the true global Rank-1 winner (`resolve_office_holder()`,
    unchanged from Phase 230) instead. **A second, always-present line**
    shows this Kingdom's own runner-up (`kingdom_runner_up()`, the real
    `nextldr` -- always scoped to this report's own Kingdom, regardless
    of whether the top line's own holder belongs to a different Kingdom
    entirely) when one exists.

    Both the top candidate's and the runner-up's own real-world standing
    are shown: `rank` (`leader_office_rank()`, the real `Rank()` --
    1 + however many other real candidates in the whole game strictly
    outscore them) and a `Riv%` figure (`office_rival_best_points()`,
    the real `ftoppts`/`rivstr` -- their own points as a percentage of
    the best score held by anyone in a *different* Kingdom, or `"None"`
    when there is no rival at all).

    **The real extra display gate** (`REPORTS.PAS` ~line 1648-1650:
    `IF ofc > Mage THEN IF bestpts < ftoppts DIV 2 THEN GOTO 90`, plus a
    second `IF bestpts < minpts[ofc] THEN GOTO 90` right after) applies
    only to the 39 offices *past* the 8 "majors" (`office.value >
    Office.MAGE.value`, `Office.MAGE.value == 7` in this project's own
    enum) -- those rows are suppressed entirely (`"None at present"`) if
    nobody at all qualifies, if the top candidate's own points are below
    half the best rival's, or if they're below `OFFICE_MIN_POINTS[office]`
    (this second check is what actually keeps a 0-point pre-election
    "Best Hope" from appearing for an extended title whose real threshold
    is nonzero, since `kingdom_best_candidate()` itself never gates on
    it). The 8
    majors keep this composer's original, simpler "show if this Kingdom
    has any candidate at all" behavior -- including, faithfully, a real
    0-point "Best Hope" row pre-election if that's genuinely this
    Kingdom's own best candidate (the real pre-election scan never gates
    on `OFFICE_MIN_POINTS` either; see `kingdom_best_candidate()`'s own
    docstring). **Post-election, the 8 majors still implicitly respect
    `OFFICE_MIN_POINTS`** through `resolve_office_holder()`'s own
    existing gate (unchanged since Phase 230, deliberately not reopened
    here) -- an asymmetry versus the pre-election path that is a direct,
    documented consequence of reusing that already-tested function for
    the post-election "true global winner" lookup, not an oversight.

    One readable line per office (`models/office.py OFFICE_NAME`, padded
    to the real 26-char field width, Phase 435), keeping this composer's
    existing "readable trailing text" convention (not the real literal
    fixed-width `Rep_Office` columns) for the new rank/percentage fields
    too -- the same "narrower than the real procedure, documented why"
    precedent every other section composer here uses.

    **Victory Points are computed but not printed inline here**, matching
    the real source exactly: `turn/victory_points.py office_victory_
    points()` (Phase 439) is a real, available function, but the actual
    `Rep_Office`/`Pray_Report` procedure never writes `ofcpoints` to the
    printed report at all -- it's an internal scoring input consumed
    elsewhere (end-game standings), not part of this letter section's own
    text. Any future end-game scoring report can call it directly.

    **Chancellor's own discovery-attribution Merit Point terms, and
    Marshal/Admiral/Defender/Priest's own battle/monster/cast tally
    counters, still read whatever `MeritTally` a caller has populated**
    (possibly all zeros) -- see `turn/merit_points.py`'s and
    `turn/office_holder.py`'s own docstrings for exactly which terms are
    fully live today versus still waiting on a future wiring phase. This
    section is not less real for that: it's the same "confirmed real
    data, some inputs still unpopulated" situation every other
    partially-wired section here already documents (e.g.
    `describe_finances_report()`'s own "Expected Expenses" gap).
    """

    lines = [_IMPERIAL_OFFICE_REPORT_HEADER]
    election_settled = state.emperor_kingdom_id is not None
    for office in ALL_OFFICES:
        office_name = f"{OFFICE_NAME[office]:<26}"
        top = resolve_office_holder(state, office) if election_settled else kingdom_best_candidate(state, office, kingdom_id)

        if top is None:
            lines.append(f"{office_name}{_IMPERIAL_OFFICE_REPORT_NONE}")
            continue

        if office.value > Office.MAGE.value:
            top_rival_points = office_rival_best_points(state, office, state.leaders[top.leader_id].kingdom_id)
            if top.merit_points < top_rival_points / 2 or top.merit_points < OFFICE_MIN_POINTS[office]:
                lines.append(f"{office_name}{_IMPERIAL_OFFICE_REPORT_NONE}")
                continue

        lines.append(_office_candidate_line(state, office, top, prefix=office_name))

        runner_up = kingdom_runner_up(state, office, kingdom_id, exclude_leader_id=top.leader_id)
        if runner_up is not None:
            lines.append(_office_candidate_line(state, office, runner_up, prefix=f"{'':26}"))

    # Phase 543: AKGEN_reverse_engineering_report (4).md SS11.3 --
    # REPORTS.PAS:1510-1517's Arcane's Valor "unification" narrative,
    # gated to the Emperor's own Kingdom report (the only one that would
    # ever see this line in the real source's own Pray_Report, since the
    # underlying NT_Owned check reads the Emperor's own inventory).
    # project-original text: no TREASURE.X2/REPORTS.PAS string survives
    # for this event anywhere in the available archive.
    if state.emperor_kingdom_id == kingdom_id and emperor_holds_arcanes_valor_unification(state):
        lines.append(
            "The Emperor's hoard of Rohan, Power, and Life artifacts is spoken of as the true Unification of Arcane's Valor."
        )
    return lines


_ADVENTURE_UNKNOWN_RICHES = f"{_ADVENTURE_BLANK_PROVINCE_COLUMNS}/Guarding unknown riches"
# Phase 430: unsourced -- no AKGEN reverse-engineering note covers how
# often the real "Special" line actually shows a feature's own treasure
# instead of "Guarding unknown riches" (the real ``trowner[fn] <>
# fn+256`` item-ownership condition this depends on is confirmed to
# exist, but not its own trigger rate). The user supplied this figure
# directly from their own real-game experience, the same "explicitly
# flagged domain-knowledge" category already used for ``worldgen/
# king_home_placement.py``'s distance/terrain rules.
_ADVENTURE_TREASURE_REVEAL_CHANCE = 0.33


def _adventure_treasure_label(treasure: Treasure, feature_id: int) -> str:
    """The real "Special" line's revealed-treasure text, e.g. "Large
    Hoard of Gold (#17): 10-25 gold" or "Reflector of Armies (#7): Cast
    "Phantasmal Armies" at skill-2" -- confirmed verbatim against real
    Turn-0 reports for both shapes. Gold hoards use their own tier name
    (``GOLD_HOARD_DISPLAY_NAME``, since ``TREASURE_NAME`` only has the
    bare "Hoard"); every other category uses ``TREASURE_NAME`` +
    ``TREASURE_LABEL`` directly. One line, not the real two (this
    module's own "readable single line" convention, already used
    throughout this composer's siblings). Indented by the real
    `_ADVENTURE_BLANK_PROVINCE_COLUMNS` 27-space width (Phase 434 --
    Phase 430 had used an unsourced 2-space indent).
    """

    if TREASURE_CATEGORY[treasure] is TreasureCategory.GOLD_HOARD:
        name = GOLD_HOARD_DISPLAY_NAME[treasure]
    else:
        name = TREASURE_NAME[treasure]
    return f"{_ADVENTURE_BLANK_PROVINCE_COLUMNS}/{name} (#{feature_id}): {TREASURE_LABEL[treasure]}"


def describe_adventure_report(state: GameState, kingdom_id: int, rng: random.Random) -> list[str]:
    """Lists every ``Feature`` this kingdom has discovered (Phase 216) --
    a deliberately narrower slice of ``REPORTS.PAS Desc_Adventure`` (the
    real "ADVENTURE" section of the end-of-turn letter report), the same
    "narrower than the real procedure, documented why" precedent
    ``describe_armies_report()`` already established for ARMIES.

    **The real procedure's province gate is a double condition this
    project doesn't model**: ``provpres[px,py] and 16`` (a per-province
    presence bitflag with no surviving definition) and, per-feature,
    ``fdis[fn] > 0`` (a *different* array from the per-kingdom
    ``fdisc``/``discovered_by_kingdom`` this project already models --
    ``models/feature.py``'s own docstring confirms its exact relationship
    to ``fdisc`` "isn't fully resolved from the available source"). This
    composer's own substitute, documented as an interpretation and not a
    citation: a feature is listed whenever ``Feature.discovery_level(
    kingdom_id) > 0`` -- the closest already-modeled analog, since a
    feature this kingdom has never discovered at all can't sensibly
    appear in its own letter regardless of the exact real gating rule.
    Every province on the map is scanned (real Pascal loops the whole
    board, not just this kingdom's own provinces -- feature discovery is
    independent of province ownership), not just this kingdom's own.

    **The "Special"/treasure line (Phase 430, previously unrendered)**:
    every discovered, non-looted feature with a real ``Feature.treasure``
    now gets a third line -- either the revealed treasure
    (``_adventure_treasure_label()``, matching real reports like "Large
    Hoard of Gold (#17): 10-25 gold" or "Reflector of Armies (#7): Cast
    "Phantasmal Armies" at skill-2" exactly) with probability
    ``_ADVENTURE_TREASURE_REVEAL_CHANCE``, or ``_ADVENTURE_UNKNOWN_RICHES``
    ("Guarding unknown riches") otherwise -- unsourced trigger rate, see
    that constant's own docstring. A feature with no recorded
    ``treasure`` (created outside world generation, e.g. most existing
    tests) always renders ``_ADVENTURE_UNKNOWN_RICHES``, matching this
    module's existing "no source, no silent default" convention rather
    than a guessed reveal. `rng` is a new required parameter for this
    reason -- every pre-Phase-430 caller must now supply one (this
    composer's own single caller, `compose_letter_report()`, already
    threads one through for its other sections).

    **Phase 434 rewrites the per-feature line to the real fixed-width
    columns** (`REPORTS.PAS Desc_Adventure`'s nested `It`/`Check_None`,
    ~lines 2012-2029), the user's own "tutto il report, pixel-perfect"
    scope decision: province name (truncated to 14, padded to 15) + one
    literal space + `province_code()` (Phase 431, unpadded -- the real
    `ps` string has no format specifier of its own) + two literal spaces
    + `%exp` (width 3, right-just.) + two literal spaces, **only on the
    first feature at a given province** -- every later feature at that
    same province gets `_ADVENTURE_BLANK_PROVINCE_COLUMNS` (27 blank
    columns) instead, matching the real `Check_None`'s own `ELSE
    WRITE('':27)` branch. Feature type (width 15), feature number (width
    3, right-just., + 2 literal spaces), then the monster column (width
    16) -- `_ADVENTURE_SACKED_AND_LOOTED` (the real, verbatim "sacked
    &looted  " literal) when looted, the guardian monster's own label
    otherwise (blank if none recorded), plus `"    ?"` (4 literal spaces
    + `?`) appended when `discovery_level(kingdom_id) == 1` (an
    unconfirmed-riches feature). All of this is now **one single line
    per feature**, not the previous three (province/feature/treasure) --
    matching the real procedure's own single-`WRITE`-sequence-per-
    feature shape; only the Special/treasure line (below) stays separate,
    since the real source does keep that as its own `WRITELN`.

    **The "Special"/treasure line (Phase 430, previously unrendered;
    Phase 434 corrects its indent)**: every discovered, non-looted
    feature with a real ``Feature.treasure`` still gets its own
    following line -- either the revealed treasure
    (``_adventure_treasure_label()``, matching real reports like "Large
    Hoard of Gold (#17): 10-25 gold" or "Reflector of Armies (#7): Cast
    "Phantasmal Armies" at skill-2" exactly) with probability
    ``_ADVENTURE_TREASURE_REVEAL_CHANCE``, or ``_ADVENTURE_UNKNOWN_RICHES``
    ("Guarding unknown riches") otherwise -- unsourced trigger rate, see
    that constant's own docstring. Both now indented by the real 27-space
    `_ADVENTURE_BLANK_PROVINCE_COLUMNS` width (`REPORTS.PAS` ~line 2089:
    `WRITELN(playfile,'':27,'/Guarding unknown riches...')`) -- Phase 430
    had used an unsourced 2-space indent. A feature with no recorded
    ``treasure`` (created outside world generation, e.g. most existing
    tests) always renders ``_ADVENTURE_UNKNOWN_RICHES``, matching this
    module's existing "no source, no silent default" convention rather
    than a guessed reveal. `rng` is a required parameter for this reason
    -- every caller must supply one (this composer's own single caller,
    `compose_letter_report()`, already threads one through for its other
    sections).

    **What this deliberately does NOT reproduce, and why**:
    - The real "Special" column's own level-2/level-3 magic-power-hint
      cases (``fdisc`` level 2/3, a per-feature ``MagicFeature`` link)
      still aren't modeled -- only level 1's ``"?"`` plus the plain
      revealed-or-hidden treasure line above.
    - The real feature-type-name truncation's own dot-insertion rule
      (`Delete`/`Insert('.',tmp,4)` for names over 14 characters
      containing a space) isn't reproduced -- this composer just
      truncates/pads to the real 15-char field width, plain.

    A feature with no ``guardian_monster`` recorded (a data gap this
    project's own ``Feature`` model allows, unlike real Pascal's always-
    populated ``fmonst`` array) renders a blank monster column, rather
    than guessing one.
    """

    lines = ["ADVENTURE", _ADVENTURE_REPORT_OPENING, _ADVENTURE_REPORT_COLUMN_HEADER]

    by_province: dict[HexCoord, list[Feature]] = {}
    for feature in state.features.values():
        if feature.discovery_level(kingdom_id) <= 0:
            continue
        by_province.setdefault(feature.coord, []).append(feature)

    if not by_province:
        lines.append(_ADVENTURE_REPORT_NONE_AT_PRESENT)
        return lines

    for coord in sorted(by_province, key=lambda c: (c.x, c.y)):
        province = state.provinces.get(coord)
        if province is not None and province.name:
            province_label = province.name
        else:
            province_label = f"({coord.x}, {coord.y})"
        explored_percent = 0
        if province is not None:
            explored_percent = province.explored_percent_by_kingdom.get(kingdom_id, 0)
        code = province_code(coord)

        for index, feature in enumerate(sorted(by_province[coord], key=lambda f: f.feature_id)):
            if index == 0:
                name_field = f"{province_label[:14]:<15}"
                prefix = f"{name_field} {code}  {explored_percent:>3}  "
            else:
                prefix = _ADVENTURE_BLANK_PROVINCE_COLUMNS

            kind_field = f"{FEATURE_TYPE_NAMES[feature.kind][:15]:<15}"
            number_field = f"{feature.feature_id:>3}  "
            if feature.looted:
                monster_field = _ADVENTURE_SACKED_AND_LOOTED
            elif feature.guardian_monster is not None:
                monster_field = f"{_adventure_monster_label(feature.guardian_monster)[:16]:<16}"
            else:
                monster_field = f"{'':<16}"

            entry = f"{prefix}{kind_field}{number_field}{monster_field}"
            if feature.discovery_level(kingdom_id) == 1:
                entry += "    ?"
            lines.append(entry)

            if not feature.looted:
                if feature.treasure is not None and rng.random() < _ADVENTURE_TREASURE_REVEAL_CHANCE:
                    lines.append(_adventure_treasure_label(feature.treasure, feature.feature_id))
                else:
                    lines.append(_ADVENTURE_UNKNOWN_RICHES)

    return lines


# HostAK/TP/REPORTS.PAS Letter_Reports/Write_Letter (~line 2364-2459) --
# the real "LETTER REPORTS" section's own sourced, verbatim strings.
_LETTER_REPORTS_OPENING = (
    "O King of Kings, thy heroes have travelled around the globe in "
    "search of adventure and conquest.  I have faithfully kept their "
    "correspondence, and now I present it to thee:"
)
_LETTER_REPORTS_NONE = "There are no letters from anyone at this time."
_LETTER_SALUTATION = "Honored Sovereign,"


def _king_leader_id(state: GameState, kingdom_id: int) -> int | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return leader.leader_id
    return None


def describe_letter_reports(
    results: list[PhaseDispatchResult],
    state: GameState,
    kingdom_id: int,
    rng: random.Random,
    *,
    ability_names: dict[Ability, str] | None = None,
    board_width: int | None = None,
) -> list[str]:
    """Assembles the "LETTER REPORTS" section (Phase 217) -- every other
    leader in this kingdom's own turn narrated as a letter addressed to
    the King.

    **`board_width` (Phase 248)**: forwarded as-is to `describe_turn_
    results()`, whose own docstring explains the opt-in -- `None` by
    default, so omitting it keeps every pre-Phase-248 caller's exact
    behavior (no rumor narration in any letter).

    **A real, sourced structural discovery, not a guess**: `REPORTS.PAS
    Write_Letter(ldr,kng,non)` -- the real per-letter procedure --
    doesn't read from any separate stored-message system. It calls
    `Tell_Story(ldr,kng)`, the *exact same* story-buffer mechanism
    `Basic_Report()` already uses to write the King's own "ACTION
    REPORT" section. A "letter" is simply another leader's own turn
    narrative, wrapped in a From/To/salutation/signature envelope --
    this project already has that narrative, via `describe_turn_results()`
    (Phase 213/214/216's own real caller), so this composer reuses it
    directly rather than needing new state.

    **Which leaders write a letter is an interpretation, not a
    citation**: the real gate is `Either_King(ldr,kng,false)`, whose own
    definition isn't in any of the 13 available `.PAS` files (confirmed
    absent, same "missing main program" category as `turn/movement.py`'s
    hex adjacency scheme). Modeled here as "every other leader recorded
    in this kingdom, excluding the King himself" -- the natural reading
    given `Letter_Reports(kng)` is called once per King and the
    surrounding code frames each letter as a Hero's own correspondence
    to his sovereign.

    **Deliberately not reproduced**:
    - `Check_Pigeons` -- a genuinely separate inter-player pigeon-message
      system (`"M>>"` records in a per-turn `KM` file) `Write_Letter`
      also calls partway through each letter. No message-store concept
      exists anywhere in this project; confirmed absent, not unwired.
    - The multi-turn backlog loop (`FOR lrt:= 0 TO gameturn DO ...
      lrecturn^[ldr] = lrt`) -- only this turn's own dispatch results
      render, the same single-turn scope `describe_turn_results()`
      itself already has.
    - The random "Squire to <leader>" alternate-authorship gimmick
      (`Aud_Rand`/`bornx`/`Company`-mode-dependent) -- needs fields this
      project doesn't track for this purpose; every letter is signed
      with the leader's own real name.

    A section header always renders (matching `Expand_Write('LETTER
    REPORTS',kng)`'s own unconditional placement before the real loop);
    the opening flavor text only appears once, before the first real
    letter -- exactly mirroring `Write_Letter`'s own `IF non THEN`
    guard -- and `_LETTER_REPORTS_NONE` (a real, sourced string) renders
    instead when no leader has anything to report.
    """

    king_leader_id = _king_leader_id(state, kingdom_id)
    king_name = state.leaders[king_leader_id].name if king_leader_id is not None else None

    # Phase 614: state.dead_leaders is included too -- otherwise a Hero
    # who died from their own action this turn (e.g. losing a Challenge)
    # never even enters other_leader_ids, silently dropping their whole
    # letter -- the same shape as compose_letter_report()'s own Phase
    # 614 fix, a distinct, separately-computed leader set this function
    # never shared with that one. remove_leader() never touches
    # .kingdom_id on the archived LeaderState.
    other_leader_ids = sorted(
        {
            leader.leader_id
            for leader in (*state.leaders.values(), *state.dead_leaders.values())
            if leader.kingdom_id == kingdom_id and leader.leader_id != king_leader_id
        }
    )

    lines = ["LETTER REPORTS"]
    letter_lines: list[str] = []
    for leader_id in other_leader_ids:
        leader_results = [entry for entry in results if entry.leader_id == leader_id]
        story_lines = describe_turn_results(
            leader_results, state, rng, ability_names=ability_names, board_width=board_width
        )
        if not story_lines:
            continue
        leader = state.leaders.get(leader_id) or state.dead_leaders.get(leader_id)
        leader_name = leader.name
        if not letter_lines:
            letter_lines.append(_LETTER_REPORTS_OPENING)
        letter_lines.append(f"From: {leader_name}")
        letter_lines.append(f"To: {king_name}" if king_name is not None else "To:")
        letter_lines.append(_LETTER_SALUTATION)
        letter_lines.extend(story_lines)
        letter_lines.append(f"Thy humble servant,   {leader_name}")

    if letter_lines:
        lines.extend(letter_lines)
    else:
        lines.append(_LETTER_REPORTS_NONE)

    return lines


# HostAK/TP/REPORTS.PAS's own "Final Standings" block (~line 1665-1690,
# 1784) computes this reduction (`outred[kalign] * diff_steps`) directly
# into each King's own per-King Final-Standings row -- the real engine
# never renders it as its own separate, labeled table. **This section
# header and framing are therefore project-original, not a Pascal
# transcription** -- flagged per this project's own standing rule for
# unsourced presentation choices. The *formula and its numeric values*
# are real and fully sourced (rulebook [10.2], `turn/emperor_election.py
# alignment_victory_point_reduction_percent()`, Phase 228; unified with
# this exact same real REPORTS.PAS formula in Phase 558) -- only the
# choice to surface it as its own standalone report section, rather than
# folded into `turn/final_standings.py`'s own composite standings (whose
# results this module still doesn't render into prose at all -- see that
# module's own docstring), is this project's own design.
_ALIGNMENT_REDUCTION_HEADER = "ALIGNMENT REDUCTION"
_ALIGNMENT_REDUCTION_INTRO = (
    "Since the Imperial election, every Kingdom's Victory Points are reduced by a "
    "percentage proportional to how far their Alignment lies from the Emperor's own:"
)


def describe_alignment_victory_point_reduction(state: GameState) -> list[str]:
    """Renders the rulebook [10.2] Alignment-distance Victory Point
    reduction table (see the module-level comment above this function for
    why the section itself is project-original even though the formula
    and values are real) -- one line per `Alignment`, ordered by
    `models/alignment.py ALIGNMENT_ORDINAL` (the real Pascal ordinal
    sequence).

    Returns an empty list before any Emperor has been elected
    (`GameState.emperor_kingdom_id is None`) -- there is no Alignment to
    measure distance from yet, and the rulebook's own reduction only ever
    applies "since the Imperial election." **Phase 558**: `alignment_
    victory_point_reduction_percent()` now covers all 10 `Alignment`
    members (a real, disassembly-sourced value exists for each), so the
    only ones still excluded here are `Mechanical`/`Special` -- reusing
    `turn/emperor_election.py _ORDINARY_ALIGNMENTS`, since those two are
    confirmed to never be a selectable Kingdom Alignment in this
    project's own data (see that tuple's own docstring), not a genuine
    formula gap the way they used to be.
    """

    if state.emperor_kingdom_id is None:
        return []

    emperor_alignment = state.kingdoms[state.emperor_kingdom_id].alignment
    lines = [_ALIGNMENT_REDUCTION_HEADER, _ALIGNMENT_REDUCTION_INTRO]
    for alignment in _ORDINARY_ALIGNMENTS:
        reduction = alignment_victory_point_reduction_percent(alignment, emperor_alignment)
        lines.append(f"{alignment.value}: -{reduction}%")
    return lines


# `VITTORIA E FINE PARTITA.txt` (user-supplied, audited Phase 558):
# "Alla fine della partita, report nell'ultimo verrà elencata la
# classifica con i punti vittoria (nome RE, nome giocatore, classifica
# dei punti vittoria...)" -- the real source (SS14.1, quoted in full in
# `turn/final_standings.py`'s own docstring) folds this into `Pray_
# Report`'s own post-coronation "unified world" mode rather than a
# separate labeled section, the same "project-original section, real
# underlying data" precedent `describe_alignment_victory_point_
# reduction()` above already established. "nome giocatore" (player
# name) is real-world moderator bookkeeping this project has never
# modeled anywhere (the same boundary already drawn for prize money,
# `turn/final_standings.py`'s own module docstring) -- omitted here,
# not guessed.
_FINAL_STANDINGS_HEADER = "FINAL STANDINGS"
_FINAL_STANDINGS_INTRO = "Now that an Emperor has been crowned, here stands the world's own final ranking:"


def _format_victory_points(points: float) -> str:
    """`points` as a plain integer when it's a whole number, else with the
    fewest decimal digits that round-trip -- `office_victory_points()`'s
    own alignment-discount multiplication can leave float noise (e.g.
    `7.6000000000000005`) that a bare `str()`/`:.2f` would either print
    verbatim or pad with a misleading trailing zero.
    """

    rounded = round(points, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def describe_final_standings_report(state: GameState) -> list[str]:
    """Renders `turn/final_standings.py compose_final_standings_report()`'s
    own computed end-of-game ranking into report prose -- see the
    module-level comment above this function for why the section itself
    is project-original even though every figure in it is real,
    previously-computed-but-never-printed data (that module's own
    docstring explicitly flagged this exact gap: "rendering these
    results into actual report prose... deliberately not attempted").

    Returns an empty list before any Emperor has been elected (the same
    gate `compose_final_standings_report()` itself uses) -- there is no
    ranking to show yet.

    One line per Kingdom, in `standings` order (rank 1 first): that
    Kingdom's own King (`_king_leader_id()`; a Kingdom currently without
    a registered King, an edge case `kingdom_points()` itself already
    scores same as any other Kingdom, shows as "no King" rather than a
    blank or guessed name) and its real `kingdom_points()` total
    (`_format_victory_points()`, since alignment-discounted office
    points can be fractional).

    Then, one instructional line per `valhalla_qualifiers` entry (real
    `qualifies_for_valhalla_induction()`: `individual_king_points >= 20`
    **or** first place -- the fuller, disassembly-sourced condition,
    not just the text's own literal ">= 20", the same precedent Phase
    558 already established for trusting the more complete sourced
    formula) -- the rulebook's own "al giocatore che ne ha ottenuti
    almeno 20 va comunicato di scrivere al GM se si vuole far entrare il
    RE nel VALHALLA e con quale oggetto posseduto all'ultimo turno" is a
    real player-facing instruction, not something this engine resolves
    on its own (which item to induct with is the player's own later
    choice, communicated out-of-band to the GM) -- only Kingdoms with a
    registered King can qualify (`qualifies_for_valhalla_induction()`'s
    own `individual_king_points()` scores a Kingless Kingdom `0.0`, and
    first-place alone doesn't bypass needing a King to name in this
    line), so a Kingless Kingdom is silently skipped here even if it
    somehow topped `standings`.
    """

    report = compose_final_standings_report(state)
    if report is None:
        return []

    lines = [_FINAL_STANDINGS_HEADER, _FINAL_STANDINGS_INTRO]
    for rank, kingdom_id in enumerate(report.standings, start=1):
        kingdom = state.kingdoms[kingdom_id]
        king_leader_id = _king_leader_id(state, kingdom_id)
        king_name = state.leaders[king_leader_id].name if king_leader_id is not None else "no King"
        points = _format_victory_points(report.kingdom_points[kingdom_id])
        lines.append(f"{rank}. {king_name} of {kingdom.name}: {points} Victory Points")

    for kingdom_id in report.valhalla_qualifiers:
        king_leader_id = _king_leader_id(state, kingdom_id)
        if king_leader_id is None:
            continue
        king_name = state.leaders[king_leader_id].name
        kingdom_name = state.kingdoms[kingdom_id].name
        lines.append(
            f"{king_name} of {kingdom_name} has earned enough Victory Points to enter Valhalla -- "
            f"write to the GM if you wish to induct them, specifying which item {king_name} held on the last turn."
        )

    return lines


# CTBOTH.PAS `seastype`/`seasname` (Phase 257) -- the `{$IFNDEF Noble}`
# branch specifically: `(Spring,ESummer,LSummer,Fall,EWinter)` /
# `('spring','early summer','late summer','fall','early winter')`.
# Confirmed live (not the `{$ELSE}` "Noble" branch, which starts with
# bare "winter" instead) by tallying every real "In <season>," phrase
# across the Desktop's own `SE3__T*.K*` sample files: "early winter"
# appears 183 times, bare "winter" never does. Doubly confirmed by
# `YAK.PAS`'s own real call site (~line 306): ``ss:= Concat('In ',
# seasname[seastype(Max(0,Min(4,_rphase)))],', ');`` -- a direct,
# clamped ordinal index into this exact table, keyed by `_rphase`, the
# same per-phase counter this project's own ``turn/turn_processor.py
# PHASE_LABELS = ("P0","P1","P2","P3","P4")`` already tracks 1:1.
SEASON_NAME: dict[int, str] = {
    0: "spring",
    1: "early summer",
    2: "late summer",
    3: "fall",
    4: "early winter",
}


# HostAK/TP/PROSE/SPRING.X/ESUMMER.X/LSUMMER.X/FALL.X/EWINTER.X (each
# header "3 1", `SAY.PAS:342-346 firstp`: `-1,0: FD('spring',S_Red,10)`
# / `1: FD('esummer',...)` / `2: FD('lsummer',...)` / `3: FD('fall',...)`
# / `4: FD('ewinter',...)`) -- the real full-sentence/prefix templates
# for the same 5 seasons `SEASON_NAME` above already names (Phase 257),
# keyed by the identical 0-4 ordinal. Phase 589. Sourced from a byte-
# faithful third-party reverse-engineering pass over the full 162-file
# prose corpus (`AKPROSE_reverse_engineering_report.md`, supplied
# directly by the user). Each catalog has 3 real choices with genuinely
# different shapes, kept as 3 parallel dicts rather than forced into one
# uniform structure:
#
# - choice 1 (`SEASON_TRANSITION_TEMPLATE`): a full "season X turned
#   into season Y" sentence. Only `SPRING.X`'s own choice 1 carries an
#   optional `<`/`>` clause ("...and < prepared to carry out > orders")
#   -- the other 4 describe the pure season transition with no
#   character subject at all, a real, confirmed asymmetry (Spring is
#   the year's first season, `firstp` -1/0, matching `YAK.PAS`'s own
#   real "start of game/year" framing already cited for `SEASON_NAME`).
# - choice 2 (`SEASON_PREFIX_TEMPLATE`): a bare "in/during <season>,_"
#   connector clause (trailing `_` = space, ready for direct
#   concatenation) -- this is the real source behind `YAK.PAS`'s own
#   already-cited `Concat('In ', seasname[...], ', ')` call site,
#   confirming `_season_phrase_for_phase_label()` below is a real but
#   simplified approximation of this real, `/R`-varied template (not
#   rewired to use it here -- that function is already tested/wired
#   into a live report path, out of scope for this phase's own sourced-
#   but-unwired-data addition).
# - choice 3 (`SEASON_ADVENT_TEMPLATE`): "with the advent of the
#   <season> season{,}_" -- again a bare connector for 4 of the 5
#   seasons, but `SPRING.X`'s own choice 3 is a full sentence with its
#   own `<`/`>` clause, the same Spring-only asymmetry as choice 1.
SEASON_TRANSITION_TEMPLATE: dict[int, str] = {
    0: "{stormy/Rfrigid }winter gave_way_to/Rmelted_into {sweet/Rfragrant "
    "}spring{, and < prepared/Rmade_ready to carry out > "
    "urgent/Rimperial orders/Rassignments}.",
    1: "windy/Rthe_wet spring blossomed_into/Rwas_followed_by "
    "{a_sultry/Ra_fragrant }early summer.",
    2: "midsummer's day/Rnight passed/Rcame_and_went and {a_hot/Ra_pleasant "
    "}late summer came/Rarrived.",
    3: "the {sultry/Rhot days of }summer surrendered_to/Rmellowed_into "
    "{a_colorful/Rthe }fall.",
    4: "the fall {season }cooled_into/Rdarkened_into {a_frigid/Rthe_stillness_of "
    "}early winter.",
}

SEASON_PREFIX_TEMPLATE: dict[int, str] = {
    0: "in spring,_",
    1: "in/Rduring early summer,_",
    2: "in late summer,_",
    3: "in/Rduring fall,_",
    4: "in/Rduring early winter,_",
}

SEASON_ADVENT_TEMPLATE: dict[int, str] = {
    0: "with the advent/Rcoming of the spring season{,} < prepared/Rset_out "
    "to quench > thirst for adventure/Rglory.",
    1: "with the advent/Rcoming of the early summer season{,}_",
    2: "with the advent/Rcoming of the late summer season{,}_",
    3: "with the advent/Rcoming of the fall season{,}_",
    4: "with the advent/Rcoming of the early winter season{,}_",
}


def _season_phrase_for_phase_label(phase_label: str) -> str:
    """"In <season>, " prefix for one GENERAL INTELLIGENCE REPORT line,
    keyed off the originating ``PhaseDispatchResult.phase_label``
    ("P0".."P4") -- see ``SEASON_NAME``'s own docstring for the sourcing.

    Returns ``""`` (no prefix, not a guess) for any label that isn't a
    real "P<N>" phase -- the synthetic entries this project's own
    ``turn_processor.py`` also produces (``"plague-spread"``,
    ``"gate-angel-visit"``, ``"forced-rebattle"``, ...) have no real
    originating phase index recoverable from this project's own data
    model, the same "no data, no guess" convention used throughout.

    **Deliberately simplified vs. the real Pascal engine, documented
    here rather than silently diverging**: `SAY.PAS` resets a
    per-kingdom `phasewrit` flag every time `_rphase` changes and only
    prints the "In <season>," prefix once per (kingdom, phase) run of
    consecutive entries, not once per entry. Reproducing that exactly
    would require re-deriving each kingdom's own consecutive-run
    grouping at render time from ``state.world_events``, which isn't
    recorded in phase order to begin with (``record_battle_world_
    events()``/``record_spell_world_events()``/``record_plague_spread_
    world_events()`` run as three separate, fixed-order passes, not a
    single phase-ordered walk) -- a real, but narrower, follow-up gap.
    This project instead prefixes every recorded line independently,
    which can occasionally show one extra "In <season>," line the real
    engine would have suppressed as a repeat within the same phase --
    the same category of accepted, flagged approximation this project's
    own Duel/retreat-destination heuristics already carry.
    """

    if not phase_label.startswith("P") or not phase_label[1:].isdigit():
        return ""
    index = int(phase_label[1:])
    season = SEASON_NAME.get(index)
    return f"In {season}, " if season is not None else ""


def _battle_reports_from_results(results: list[PhaseDispatchResult]) -> list[tuple[str, BattleReport]]:
    """Every ``(phase_label, BattleReport)`` pair reachable from ``results``
    -- a battle can surface three different ways depending which real call site produced
    it (``turn/turn_processor.py``'s own docstring lists all four:
    ``move_execution.py execute_move()`` wraps it as
    ``MoveExecutionResult.battle_report``, ``pursue_execution.py
    execute_pursue()`` as ``PursueExecutionResult.battle_report``, the
    Multiple Contingents fan-out as ``MultiAttackerMoveResult.battle.
    report``, and ``_dispatch_contested_rebattles`` passes the
    ``BattleReport`` itself as ``PhaseDispatchResult.result`` directly)
    -- rather than depend on any one of those result types by name (a
    layering a report-composer module shouldn't take on), this just
    duck-types the three shapes. **Phase 257**: now also returns each
    report's own originating ``entry.phase_label``, so a caller can
    resolve a season prefix for it (``_season_phrase_for_phase_label()``)
    -- ``PhaseDispatchResult`` already stamps every entry with this, no
    new data needed.
    """

    reports: list[tuple[str, BattleReport]] = []
    for entry in results:
        result = entry.result
        if isinstance(result, BattleReport):
            reports.append((entry.phase_label, result))
            continue
        battle_report = getattr(result, "battle_report", None)
        if isinstance(battle_report, BattleReport):
            reports.append((entry.phase_label, battle_report))
            continue
        battle = getattr(result, "battle", None)
        nested_report = getattr(battle, "report", None) if battle is not None else None
        if isinstance(nested_report, BattleReport):
            reports.append((entry.phase_label, nested_report))
    return reports


def record_battle_world_events(state: GameState, results: list[PhaseDispatchResult], rng: random.Random) -> None:
    """Populates ``state.world_events`` (Phase 231) from every battle
    found in ``results`` (``turn/turn_processor.py run_turn()``'s own
    return value) -- the one real event *source* this project wires for
    GENERAL INTELLIGENCE REPORT so far. See ``describe_general_
    intelligence_report()``'s own docstring for the full list of
    confirmed-real, still-deferred event types (movement, plagues,
    terrain illusions, cast spells...).

    **Must be called exactly once per turn, before any
    ``compose_letter_report()`` call for that turn** -- world events are
    turn-global, not per-kingdom, so calling this once per King (the way
    every other section composer here is called) would duplicate every
    entry once per King. This mirrors ``run_turn()`` itself: a single
    call whose output every King's own report composition then reads.

    **Only the battle-winner sentence is recorded, not the fuller
    per-column clash narrative** ``describe_battle()`` can also render.
    This is a deliberate, narrower slice, not an oversight: the real
    fixture text's own richest example (`SE3__T2.K2` line 506, "Circe
    (#8)... invaded Big Sky... Big Sky was overrun by Circe (#8)'s men
    in a hard-fought campaign") is exactly this outer summary sentence
    (`render_battle_winner()`'s own template), built from King/province
    names alone. The per-column clash sentences additionally need
    per-army display names -- as of Phase 236, `describe_battle()`
    synthesizes those itself (`build_battle_army_names()`, via
    `models/army_naming.py make_army_name()`), so this dispatch's own
    remaining gap is purely the missing `BattleReport` (see the note
    above this one).

    A battle with no ``BattleReport.defender_kingdom_id`` (an unowned
    province defended by some kingdom's stray garrison -- a real
    possibility ``fight_battle()``'s own exploration-advantage comment
    already allows for, see that module's docstring) is skipped: there
    is no "Kingdom of X:" owner to attribute the event to, and inventing
    one isn't warranted for what should be a rare edge case.

    **Phase 257**: every recorded line is now prefixed with its own "In
    <season>, " (``_season_phrase_for_phase_label()``) -- see that
    function's own docstring for the sourcing and the documented
    per-phase-dedup simplification.
    """

    for phase_label, battle_report in _battle_reports_from_results(results):
        coord = battle_report.province_coord
        if coord is None or battle_report.attacker_kingdom_id is None or battle_report.defender_kingdom_id is None:
            continue
        province = state.provinces.get(coord)
        is_sea = province is not None and province.effective_terrain() == Terrain.SEA
        winner_sentence = render_battle_winner(
            battle_report.battle_result,
            _diplomacy_entry(state, battle_report.attacker_kingdom_id),
            _diplomacy_entry(state, battle_report.defender_kingdom_id),
            _province_label(state, coord),
            rng,
            is_sea=is_sea,
        )
        if winner_sentence is not None:
            prefix = _season_phrase_for_phase_label(phase_label)
            state.record_world_event(coord, [prefix + winner_sentence])


# HostAK/TP/SAY.PAS `_SPlague`/`_PPlague` (Phase 232) -- the province-
# wide, "commonly known" (`S_Comm`) Plague notice, confirmed real and
# distinct from `SPELL_CAST_ANNOUNCEMENT[Spell.PLAGUE]` (a private,
# army-list-carrying first-person announcement `describe_cast()`
# already renders into the *caster's own* LETTER REPORTS entry). Two
# real, interchangeable templates were found in `SAY.PAS`
# (`_SPlague: Say('@ was hit by a plague.',S_Comm)` and `_PPlague:
# Say('plague ravaged the province of @.',S_Comm)`) -- `_SPlague`'s own
# wording is used here since it matches the real fixture text verbatim
# (`SE3__T1.K8`'s own GENERAL INTELLIGENCE REPORT: "Transylvania was
# hit by a plague."); `_PPlague`'s own trigger condition (`_P`-prefixed
# names elsewhere in `SAY.PAS` mark a distinct, more severe story path)
# isn't recoverable from the available fragments, so it's transcribed
# here as a documented alternative, not asserted as the one this project
# actually uses.
PLAGUE_WORLD_EVENT_TEMPLATE = "@ was hit by a plague."


def render_plague_world_event(province_name: str, rng: random.Random) -> str:
    """Renders `SAY.PAS` `_SPlague`'s own commonly-known Plague notice."""

    return render(PLAGUE_WORLD_EVENT_TEMPLATE, {"@": province_name}, rng=rng)


def render_illus_terrain_world_event(
    real_terrain_name: str, province_name: str, fake_terrain_name: str, rng: random.Random
) -> str:
    """Renders `SAY.PAS` `_STerIl`'s own commonly-known (`S_Comm`) Illusory
    Terrain notice (Phase 232) -- `Say(Concat('the ',
    tername[pterr[_px,_py]],' terrain of @ was magically made to appear
    as \\`.'),S_Comm)`. Distinct from `SPELL_CAST_ANNOUNCEMENT[Spell.
    ILLUS_TERRAIN]` the same way Plague's two templates are (the
    caster's own private announcement vs. this public one).
    ``real_terrain_name`` is spliced in directly via Python
    string-formatting rather than a `render()` marker -- the source
    itself builds it via a raw Pascal `Concat`, not a `PROSE.TXT`-style
    template marker, so `@`/`` are the only two real markers here,
    matching `render_cast_announcement()`'s own province_name/
    terrain_name pairing for the same spell.
    """

    template = f"the {real_terrain_name} terrain of @ was magically made to appear as `."
    return render(template, {"@": province_name, "`": fake_terrain_name}, rng=rng)


# HostAK/TP/SAY.PAS `_SFlood` (Phase 235) -- the commonly-known (`S_Comm`)
# Flood notice, confirmed real and distinct from `SPELL_CAST_
# ANNOUNCEMENT[Spell.FLOOD]` ("the Flood slowed ^L= in @, causing them
# to lose one movement point.", the *army-slowing* side effect this
# project doesn't model -- see `turn/cast_execution.py _execute_flood()`'s
# own docstring). `_SFlood` is the separate, real, terrain-only bystander
# notice matching what `_execute_flood()` actually does
# (`province.terrain_override = Terrain.SEA`).
FLOOD_WORLD_EVENT_TEMPLATE = "@ was magically flooded."


def render_flood_world_event(province_name: str, rng: random.Random) -> str:
    """Renders `SAY.PAS` `_SFlood`'s own commonly-known Flood notice."""

    return render(FLOOD_WORLD_EVENT_TEMPLATE, {"@": province_name}, rng=rng)


# HostAK/TP/SAY.PAS `_SPart`/`_SQuake` (Phase 235) -- confirmed real via
# `PROCEDURE Sps(sp: spell; fam: integer); BEGIN FD('c:\\tp\\prose\\
# spnote.x2',fam,1001+ord(sp)); END;` (line 241): `Sps(Part_Sea,S_Comm)`
# and `Sps(Earthquake,S_Comm)` both dispatch through `SPNOTE.X2` at
# `1001+ord(spell)` -- the *exact same* per-spell index this project's
# own `SPELL_CAST_ANNOUNCEMENT` dict (Phase 122) was already extracted
# from. Unlike `render_cast_announcement()`'s own call sites,
# `Sps(sp,fam)` is dispatched with no preceding "< cast a ~ spell and"
# opening clause -- confirmed by its own real call site sitting in a
# separate section of `SAY.PAS`'s dispatch table from `_LCast1`'s own
# caster-announcement group -- so a bystander sees only the bare effect
# text. Only Part_Sea ("the waters of @ were magically parted.") and
# Earthquake ("@ was devastated by an earthquake!") are used here: both
# real `SPELL_CAST_ANNOUNCEMENT` entries need nothing but `@` (no
# caster/army-list marker), confirming they're safe to render standalone
# this way -- every other `Sps(...)`-dispatched spell either isn't
# `S_Comm` (`Skeletal_Army`/`Tornado`/`Illus_Armies` are `S_AA`;
# `Charm`/`Resurrection`/`Clairvoyance`/the personal-combat spells are
# `S_PCom`; `Oratory`/`Hide_Feature`/`Kill_Enemy` are `S_Adv`) or would
# need a marker this project can't supply standalone (`Bless` is
# `S_Admin`, arguably commonly-visible in spirit, but not confirmed
# `S_Comm` in the source, so not added here).
_BYSTANDER_SPELL_NOTICE_SPELLS = frozenset({Spell.PART_SEA, Spell.EARTHQUAKE})


def render_bystander_spell_notice(spell: Spell, province_name: str, rng: random.Random) -> str:
    """Renders one of the `Sps(sp,S_Comm)`-dispatched bystander notices --
    see the module-level comment above for which spells this covers and
    why. Raises for any other spell, the same fail-loud stance
    `render_cast_announcement()` already takes for a missing marker.
    """

    if spell not in _BYSTANDER_SPELL_NOTICE_SPELLS:
        raise ValueError(f"{spell!r} has no confirmed S_Comm bystander notice")
    return render(SPELL_CAST_ANNOUNCEMENT[spell], {"@": province_name}, rng=rng)


def record_spell_world_events(
    state: GameState, results: list[PhaseDispatchResult], rng: random.Random, *, board_width: int = NORMAL_MAP_BOUNDS[0]
) -> None:
    """Populates ``state.world_events`` (Phase 232, extended Phase 235)
    from every successful province-effect cast found in ``results`` --
    the second real event *source* wired for GENERAL INTELLIGENCE
    REPORT, alongside ``record_battle_world_events()`` (Phase 231). Both
    functions share the same "call once per turn, before any
    `compose_letter_report()` call" contract -- see that function's own
    docstring for why.

    **Five spells covered as of Phase 235**: Plague, Illusory Terrain
    (Phase 232), Flood, Part Sea, and Earthquake (Phase 235) -- every
    real, `S_Comm`-tagged ("commonly known") province-effect spell found
    in `SAY.PAS`, confirmed by directly reading every `S_Comm`-tagged
    `Say()`/`Sps()` call in the file (not just the ones already known
    about). Each one's own `_execute_*()` function already stores
    everything this needs directly on `ProvinceState`
    (`illusory_terrain`/`terrain_override`/`tax_modifier_percent`) or
    needs nothing beyond the province itself (Plague/Flood/Part_Sea/
    Earthquake all have no state to read back -- their own effect
    *is* the notice, not a separately-flagged condition the way
    Illusory Terrain's fake terrain choice is).

    **Why not the other cast spells**: every other real `Sps(...)`
    dispatch in `SAY.PAS` is tagged a narrower severity than `S_Comm`
    -- confirmed by reading every `Sps(...)` call site directly, not
    assumed: Skeletal Army/Tornado/Illusory Armies are `S_AA` (kingdom-
    only, needing this project's still-missing army-naming system
    besides), Charm/Resurrection/Clairvoyance/the personal-combat
    spells are `S_PCom`, Oratory/Hide_Feature/Kill_Enemy are `S_Adv`,
    Bless is `S_Admin` (plausibly commonly-visible in spirit, but not
    confirmed `S_Comm` in the source, so not guessed here). See
    `render_bystander_spell_notice()`'s own module-level comment for
    the full breakdown.

    ``CastExecutionResult`` itself carries no caster/coord -- ``leader_
    id`` comes from the owning ``PhaseDispatchResult`` (each entry is
    already stamped with which leader dispatched it), and the target
    coord is re-decoded from ``request.target`` via the same
    ``decode_hex_number()`` `turn/cast_execution.py _resolve_province_
    target()` itself uses -- safe to redo here without re-validating
    adjacency, since ``result.applied`` being `True` already proves the
    original resolution succeeded.

    **Phase 257**: every recorded line is now prefixed with its own "In
    <season>, " (``_season_phrase_for_phase_label()``), keyed off this
    entry's own ``phase_label`` -- see that function's own docstring.
    """

    for entry in results:
        result = entry.result
        if not isinstance(result, CastExecutionResult) or not result.applied:
            continue
        request = result.request
        coord = decode_hex_number(request.target, board_width)
        province = state.provinces.get(coord)
        if province is None:
            continue
        province_name = _province_label(state, coord)
        prefix = _season_phrase_for_phase_label(entry.phase_label)

        if request.spell is Spell.PLAGUE:
            state.record_world_event(coord, [prefix + render_plague_world_event(province_name, rng)])
        elif request.spell is Spell.ILLUS_TERRAIN and province.illusory_terrain is not None:
            line = render_illus_terrain_world_event(
                TERRAIN_NAME[province.terrain], province_name, TERRAIN_NAME[province.illusory_terrain], rng
            )
            state.record_world_event(coord, [prefix + line])
        elif request.spell is Spell.FLOOD:
            state.record_world_event(coord, [prefix + render_flood_world_event(province_name, rng)])
        elif request.spell in _BYSTANDER_SPELL_NOTICE_SPELLS:
            line = render_bystander_spell_notice(request.spell, province_name, rng)
            state.record_world_event(coord, [prefix + line])


def record_plague_spread_world_events(state: GameState, results: list[PhaseDispatchResult], rng: random.Random) -> None:
    """Populates ``state.world_events`` (Phase 234) from every province
    Plague newly reached this turn via ``turn/plague_spread.py resolve_
    plague_spread()`` -- the third real event *source* wired for GENERAL
    INTELLIGENCE REPORT, alongside ``record_battle_world_events()``
    (Phase 231, battles) and ``record_spell_world_events()`` (Phase 232,
    the original Plague/Illusory Terrain casts). Same "call once per
    turn, before any ``compose_letter_report()`` call" contract as
    those two.

    ``turn/turn_processor.py run_turn()`` wraps each newly-infected
    coordinate ``resolve_plague_spread()`` returns into its own
    ``PhaseDispatchResult`` (``phase_label="plague-spread"``, ``result``
    = the bare ``HexCoord``) -- this function just filters `results` for
    that label and renders the same real, `S_Comm`-tagged notice
    ``record_spell_world_events()`` already uses for a direct cast
    (`render_plague_world_event()`, `SAY.PAS` `_SPlague`): the rulebook
    and the real fixture text draw no distinction between a province
    afflicted by a direct cast versus one reached by the spread
    mechanic -- both are simply "hit by a plague."

    **Phase 257**: unlike the other two recorders, this one's own lines
    are never given an "In <season>, " prefix -- ``phase_label`` here is
    always the synthetic ``"plague-spread"``, not a real "P<N>" phase,
    so ``_season_phrase_for_phase_label()`` always returns ``""`` for it
    (no originating phase index survives this synthetic pass; see that
    function's own docstring).
    """

    for entry in results:
        if entry.phase_label != "plague-spread":
            continue
        coord = entry.result
        province_name = _province_label(state, coord)
        state.record_world_event(coord, [render_plague_world_event(province_name, rng)])


# HostAK/TP/SAY.PAS `_LFly` (Phase 257) -- a single, real, hardcoded
# `S_Army`-tagged notice (no file): "< flew/Rrode_>_flying_armies
# into/Rover_to @." Confirmed real and confirmed cross-kingdom-visible
# directly against the Desktop's own sample files (e.g. `SE3__T10.K5`
# line 459's own GENERAL INTELLIGENCE REPORT: "In late summer,
# Tlazolteotl (#88) flew over to Waterford.") -- third person, "(#N)",
# grouped under "Kingdom of X (#N):", the same shape every other world
# event here already uses, confirming this is genuinely GIR content and
# not just the mover's own private ACTION REPORT narration.
#
# **`S_Army` sits below this project's own established `S_Comm`
# threshold** (`CTBOTH.PAS`'s own severity scale, `S_Prev=0 ...
# S_Admin=7, S_Army=8, S_Comm=9, S_IDipl=10` -- confirmed ordinal, not
# independent categories) that every other world-event source here
# (Phases 231-235) was built against. The real fixture evidence above
# is unambiguous, though: this content unmistakably reaches other
# kingdoms' own GIR feeds. Read together, these confirm the true cutoff
# for GIR visibility is "S_Army or higher," not "S_Comm only" -- the
# earlier phases' own restriction was an incomplete generalization
# (nothing S_Army-tagged had been checked against a real GIR fixture
# until now), not a wrong one for what it *did* cover. **Not a full
# resolution**: `SAY.PAS` has other `S_Army`-tagged notices (a much
# larger real per-battle narrative cluster --
# `FD('invas'/'conq'/'invwin'/'defwin'/'heavp', S_Army, ...)` -- plus
# Scar Terrain's own bystander notice, `_STZero`/`_STFite`) that stay
# unwired here, not because they fail this now-corrected threshold, but
# because each still needs its own separate research (the battle
# cluster dispatches to un-read `PROSE/*.X2` files and likely needs
# per-army names, the same gap already flagged for `describe_battle()`;
# Scar Terrain's own collapse effect is a pure function this project
# never auto-invokes, since nothing here can supply its own real
# precondition -- see `turn/cast_execution.py``_execute_scar_terrain``'s
# own docstring). Movement is the one `S_Army` notice with both a
# confirmed template *and* real execution-layer data already available
# to trigger it correctly.
#
# **The trigger condition for `_LFly` over the ordinary, `S_Admin`-tagged
# `_LMarch` is not recoverable from the available archive** -- the
# `Imp_Code` dispatch that actually chooses between them lives in the
# missing main program, the same "driver lost, callee kept" category
# already documented for hex adjacency (`turn/movement.py`) and world
# generation. **Confirmed directly with the user (project author)**: this
# module instead uses a documented, unsourced-but-reasonable heuristic --
# a move renders as "flew" when every army the mover brought to the
# destination is an overflight type (`models/army_type.py
# is_overflight_unit()`, the same table already used for rear-targeting
# eligibility in battle), matching the real fixtures' own pattern of the
# same character consistently "flying" turn after turn (a persistent
# army-composition property, not a one-off random roll). A mover with no
# overflight-only army at the destination (including one traveling with
# no army at all) falls through to the ordinary, private `_LMarch`
# narration this project already renders via `render_march()` --
# unaffected by this addendum, and never itself GIR-visible.
#
# **`_LWWalk` (Mystic Winds wind-walking, the other `S_Army`-tagged
# movement notice) -- closed, Phase 634.** Its own real trigger,
# `LeaderState.mystic_winds_active` (Phase 204), is a single per-leader
# flag with no record of *which* move it was set during, and the real
# effect lasts until the leader's own next battle (`turn/battle_
# orchestrator.py fight_battle()`'s own Phase 250 clearing), not just
# one move -- so reading the flag's own *current* value here, post-turn,
# could miss an earlier move that happened before a later, same-turn
# battle cleared it. `turn/move_execution.py MoveExecutionResult.wind_
# walking` (Phase 634) closes this: snapshotted at the *start* of each
# `execute_move()` call, before that same call's own `fight_battle()`
# (if any) can clear it -- correct even when the triggering move is the
# one that ends the spell. Not extended to `turn/turn_processor.py`'s
# own multi-attacker LMOVE path (a separate `resolve_move()`/
# `fight_multi_attacker_battle()` route that never calls
# `execute_move()` at all) -- a `MultiAttackerMoveResult` simply has no
# `wind_walking` attribute, so `getattr(..., False)` below cleanly
# falls through to the ordinary overflight check for that path,
# matching this project's own "documented narrower scope" convention.
_FLY_MOVE_TEMPLATE = "< flew/Rrode_>_flying_armies into/Rover_to @."

# `SAY.PAS` line 470, verbatim: `_LWWalk: Say('< rode_the_Mystic_Winds/
# Rwind-walked into/Rover @.',S_Army)` -- the same real-transcription
# standard `_FLY_MOVE_TEMPLATE` above was already shipped under (no
# real turn-report sample confirms either one's exact wording; both are
# direct Pascal transcriptions, not fixture-derived).
_WIND_WALK_MOVE_TEMPLATE = "< rode_the_Mystic_Winds/Rwind-walked into/Rover @."


def render_fly_move_world_event(character_name: str, province_name: str, rng: random.Random) -> str:
    """Renders `SAY.PAS` `_LFly`'s own notice for a Move -- see the
    module-level comment above for the sourcing, the corrected `S_Army`
    GIR-visibility threshold, and the documented overflight-army
    heuristic that decides when this renders instead of the ordinary,
    private `_LMarch` narration.
    """

    values = {"<": character_name, "@": province_name, ">": f"{character_name}'s"}
    return render(_FLY_MOVE_TEMPLATE, values, rng=rng)


def render_wind_walk_move_world_event(character_name: str, province_name: str, rng: random.Random) -> str:
    """Renders `SAY.PAS` `_LWWalk`'s own notice for a Move made under
    Mystic Winds -- see the module-level comment above `_FLY_MOVE_
    TEMPLATE` for the real trigger (`MoveExecutionResult.wind_walking`)
    and why `record_move_world_events()` checks it ahead of the ordinary
    overflight-army heuristic.
    """

    values = {"<": character_name, "@": province_name}
    return render(_WIND_WALK_MOVE_TEMPLATE, values, rng=rng)


def record_move_world_events(state: GameState, results: list[PhaseDispatchResult], rng: random.Random) -> None:
    """Populates ``state.world_events`` (Phase 257) from every Move whose
    mover was under Mystic Winds (Phase 634) or whose entire arriving
    force is overflight-capable -- the fourth real event *source* wired
    for GENERAL INTELLIGENCE REPORT, alongside ``record_battle_world_
    events()``/``record_spell_world_events()``/``record_plague_spread_
    world_events()``. Same "call once per turn, before any ``compose_
    letter_report()`` call" contract as those three.

    Duck-types ``result.moved``/``result.new_location``/``result.wind_
    walking`` the same way ``_battle_reports_from_results()`` duck-types
    battle shapes -- ``MoveExecutionResult`` and ``turn/turn_processor.py
    MultiAttackerMoveResult`` both carry ``moved``/``new_location`` under
    the same names, but only ``MoveExecutionResult`` has ``wind_
    walking`` (see module-level comment for why that's the correct,
    documented scope, not an oversight). Reads each mover's own armies
    from ``GameState`` *after* the whole turn has resolved (``state.
    armies_commanded_by(entry.leader_id)``, filtered to ``new_location``)
    rather than from the move result itself (neither result type stores
    which army ids moved) -- safe, since a later phase reassigning
    command (Leave/Pick_Up) is a real, if rare, possibility this reads
    around simply by asking "who commands what, right now" rather than
    "what did this one phase's own army list say."

    A mover with no armies at ``new_location``, who wasn't wind-walking,
    and whose armies aren't *all* overflight-capable, is skipped
    entirely -- no event, matching the ordinary march staying private
    (see module-level comment).
    """

    for entry in results:
        result = entry.result
        moved = getattr(result, "moved", None)
        new_location = getattr(result, "new_location", None)
        if not moved or new_location is None:
            continue
        armies = [army for army in state.armies_commanded_by(entry.leader_id) if army.location == new_location]
        if not armies:
            continue
        leader = state.leaders.get(entry.leader_id)
        if leader is None:
            continue
        province_name = _province_label(state, new_location)
        prefix = _season_phrase_for_phase_label(entry.phase_label)
        if getattr(result, "wind_walking", False):
            line = render_wind_walk_move_world_event(leader.name, province_name, rng)
        elif all(is_overflight_unit(army.army_type) for army in armies):
            line = render_fly_move_world_event(leader.name, province_name, rng)
        else:
            continue
        state.record_world_event(new_location, [prefix + line])


def record_uncontested_conquest_world_events(state: GameState, results: list[PhaseDispatchResult], rng: random.Random) -> None:
    """Populates ``state.world_events`` (Phase 410) from every Move that
    conquered a province with no battle at all -- the fifth real event
    *source* wired for GENERAL INTELLIGENCE REPORT, alongside
    ``record_battle_world_events()``/``record_spell_world_events()``/
    ``record_plague_spread_world_events()``/``record_move_world_events()``.
    Same "call once per turn, before any ``compose_letter_report()`` call"
    contract as those four.

    ``render_uncontested_conquest()`` (``HostAK/TP/PROSE/CONQ.X``, Phase
    63) had been fully built since Phase 63 with nothing to feed it --
    no code path ever produced a real uncontested conquest until Phase
    410 wired the mechanic itself into ``turn/move_execution.py
    execute_move()`` (see that function's own Phase 410 addendum).
    ``result.conquered and result.battle_report is None`` is exactly
    that case -- a battle-won conquest (``battle_report`` present) is
    already covered by ``record_battle_world_events()``'s own winner
    sentence and must not be double-recorded here.

    Duck-types ``result.moved``/``result.conquered``/``result.battle_
    report``/``result.new_location`` the same way ``record_move_world_
    events()`` does -- only ``turn/move_execution.py
    MoveExecutionResult`` carries ``conquered`` today (``turn_processor.py
    MultiAttackerMoveResult`` always goes through a real battle, so it
    never needs this path), but duck-typing keeps this consistent with
    every other recorder here rather than importing a concrete type to
    ``isinstance``-check.
    """

    for entry in results:
        result = entry.result
        if not getattr(result, "conquered", False) or getattr(result, "battle_report", None) is not None:
            continue
        new_location = getattr(result, "new_location", None)
        if new_location is None:
            continue
        leader = state.leaders.get(entry.leader_id)
        province = state.provinces.get(new_location)
        if leader is None or province is None:
            continue
        province_name = _province_label(state, new_location)
        is_sea = province.effective_terrain() == Terrain.SEA
        prefix = _season_phrase_for_phase_label(entry.phase_label)
        line = render_uncontested_conquest(leader.name, province_name, rng, is_sea=is_sea)
        state.record_world_event(new_location, [prefix + line])


_GENERAL_INTELLIGENCE_REPORT_HEADER = "GENERAL INTELLIGENCE REPORT"
_GENERAL_INTELLIGENCE_REPORT_NONE = "None at present"


def describe_general_intelligence_report(state: GameState, kingdom_id: int) -> list[str]:
    """Assembles the "GENERAL INTELLIGENCE REPORT" section (Phase 231) --
    the real cross-kingdom world-news feed, confirmed directly from
    ~15 real `SE3__T*.K*` fixture files: one `Kingdom of <Name> (#<id>):`
    block per foreign kingdom whose activity this kingdom can see this
    turn, each followed by that kingdom's own narrative lines.

    **Reads ``state.world_events`` -- already populated by separate,
    explicit ``record_battle_world_events()``/``record_spell_world_
    events()``/``record_plague_spread_world_events()`` calls for this
    whole turn** (see those functions' own docstrings for why they
    can't be called from here, once per King). This composer only
    filters and groups what's already there.

    **Visibility**: `turn/world_events.py is_visible_to()` -- rulebook
    [1.4], a province this kingdom owns or one adjacent to it.

    **Grouping key**: each visible event's own province's *current*
    `owner_kingdom_id`, read at render time (after the whole turn's
    battles have resolved) -- not the event's own recorded attacker/
    defender. Confirmed against real fixture text: `SE3__T2.K2`'s own
    "Kingdom of Circe (#8): ...Big Sky was overrun by Circe (#8)'s
    men..." files the event under the post-battle *winner*'s name even
    though the same paragraph identifies Aegir (#66) as Big Sky's
    pre-battle owner; `SE3__T11.K6`'s own back-and-forth Rejaf paragraphs
    (Giovanna (#7) conquers it, then Uga-Buga Makumb (#1) re-conquers it)
    are filed entirely under "Kingdom of Uga-Buga Makumb (#1):" -- the
    province's owner *by the end of that block*. Reading
    `ProvinceState.owner_kingdom_id` fresh at render time reproduces both
    examples directly, with no separate "who's this filed under" field
    needed on `WorldEvent` itself.

    A visible event whose province currently has no owner
    (`owner_kingdom_id is None`, e.g. its own conqueror was later wiped
    out) or is currently owned by ``kingdom_id`` itself (that's this
    kingdom's *own* activity, already covered by its other sections, not
    foreign news) is skipped, not force-filed anywhere.

    **Deliberately narrow event-source scope, the same "documented, not
    silent" precedent every other section composer here already
    follows.** The real letters show many distinct event types --
    movement ("X flew over to Y"), plagues, terrain illusions, Skeletal
    Army risings, other cast-spell narrations, and a much richer
    per-battle narrative -- and as of Phase 410 this project populates
    five real sources across seven call sites: battle results
    (`record_battle_world_events()`), five real `S_Comm` province-effect
    casts -- Plague, Illusory Terrain, Flood, Part Sea, Earthquake
    (`record_spell_world_events()`, Phases 232/235) -- Plague's own
    spread-to-adjacent-provinces mechanic
    (`record_plague_spread_world_events()`, Phase 234, reusing Plague's
    own real notice text -- the rulebook draws no distinction between a
    directly-cast and a spread-caused affliction), Movement
    (`record_move_world_events()`, Phase 257 -- see that function's own
    module-level comment for the corrected "`S_Army` or higher, not
    `S_Comm`-only" GIR-visibility threshold this discovery required, the
    documented overflight-army heuristic that decides "flew" vs. the
    ordinary private march, and (Phase 634) Mystic Winds wind-walking's
    own matching `S_Army` notice), and uncontested conquest
    (`record_uncontested_conquest_world_events()`, Phase 410 -- see that
    function's own docstring for why nothing fed
    `render_uncontested_conquest()`'s already-built CONQ.X template
    until the underlying ownership-transfer mechanic itself was wired
    into `turn/move_execution.py execute_move()` the same phase).

    **`S_AA`-tagged content (Skeletal Army risings, `_ARises:
    Sps(Skeletal_Army,S_AA)`) is still correctly excluded even under
    the "`S_Army` or higher" threshold**: `S_AA`'s own ordinal (6) sits
    below `S_Army`'s (8) on `CTBOTH.PAS`'s own severity scale, so this
    was never a false negative from the old "`S_Comm`-only" restriction
    -- genuinely narrower-than-`S_Army` content, confirmed, not merely
    unconsidered (Skeletal Army would also need this project's
    still-missing army-naming system, a second, independent reason).
    Every other spell without a confirmed `S_Army`-or-higher `SAY.PAS`
    notice (the personal-combat spells already covered by the encounter
    engine, Bless's plausible-but-unconfirmed `S_Admin`, ...) is
    likewise a confirmed-real, deliberately-deferred follow-up.

    **Scar Terrain's own bystander notice (`_STZero`/`_STFite`,
    `SAY.PAS` ~747-748) is confirmed real text -- both are inline
    `Say()` strings, not missing `PROSE/*.X2` files -- but investigated
    (Phase 411) and found permanently unreachable from this project's
    own state, not merely unwired.** Both notices fire only when
    `turn/cast_execution.py scar_terrain_collapse()` actually runs, and
    that function is never called from any real dispatch path: its own
    precondition, "when the tax base reaches 0 gold"
    (`scar_terrain_is_exhausted()`), needs a real per-province tax base
    to check against, and this project has no tax/revenue-collection
    system anywhere to supply one (the same gap `ProvinceState.tax_
    modifier_percent`'s own docstring already flags). `_STFite`'s own
    land-collapse race choice is separately unspecified by the rulebook
    itself ("usually by immigration from an adjacent province" names an
    external fact, not a formula) -- see `_execute_scar_terrain()`'s own
    docstring for both points in full. A world-events recorder for this
    notice would have nothing to call it from until a real tax system
    exists; not attempted here.

    **The rest of the `S_Army`-tagged per-battle narrative cluster
    (`FD('invas'/'conq'/'invwin'/'defwin', S_Army, ...)`) is not a
    remaining gap, it's a closed question**: `WINNER.X`/`DEFWIN.X` were
    already ported as `render_battle_winner()` (Phase 61) and `CONQ.X`
    as `render_uncontested_conquest()` (Phase 63) -- `record_battle_
    world_events()`'s own docstring documents, against real fixture
    text (`SE3__T2.K2`), that the richer per-column clash narrative
    `describe_battle()` can also render (`_BClash`/`_BRes`, `invas`'s
    own opening line, commander names, the `_BConq` tax-base reveal)
    genuinely doesn't appear in real GIR paragraphs -- only the outer
    winner/conquest sentence does. Phase 410 confirmed this holds for
    uncontested conquest too, by construction: `render_uncontested_
    conquest()` renders the exact same outer-sentence shape as `render_
    battle_winner()`, just for the no-battle case.

    Always returns at least the header + "None at present" fallback
    (the same convention `describe_diplomacy_report()`/`describe_
    imperial_office_report()` already use), never a bare empty list --
    the real section header appears in every real fixture file checked.
    """

    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    groups: dict[int, list[str]] = {}
    order: list[int] = []
    for event in state.world_events:
        if not is_visible_to(state, kingdom_id, event.coord, bounds):
            continue
        province = state.provinces.get(event.coord)
        owner = province.owner_kingdom_id if province is not None else None
        if owner is None or owner == kingdom_id:
            continue
        if owner not in groups:
            groups[owner] = []
            order.append(owner)
        groups[owner].extend(event.lines)

    lines = [_GENERAL_INTELLIGENCE_REPORT_HEADER]
    if not groups:
        lines.append(_GENERAL_INTELLIGENCE_REPORT_NONE)
        return lines
    for owner in order:
        lines.append(f"Kingdom of {_diplomacy_entry(state, owner)}:")
        lines.extend(groups[owner])
    return lines


def compose_letter_report(
    results: list[PhaseDispatchResult],
    state: GameState,
    kingdom_id: int,
    rng: random.Random,
    *,
    ability_names: dict[Ability, str] | None = None,
    board_width: int | None = None,
) -> list[str]:
    """Assembles a single King's own end-of-turn letter report (Phase 215) by
    stitching together this project's already-built section composers, in
    the real section order -- confirmed directly against actual generated
    turn-report output, not guessed: the Desktop's real `SE3__T*.K*` files
    (e.g. `SE3__T2.K2`, section headers at lines 31/174/313/319/352/367/
    416/450/471/491/506) show ACTION REPORT, LETTER REPORTS, STATE OF THE
    NATION, DIPLOMACY, FINANCES, PROVINCES, CHARACTERS, ARMIES, IMPERIAL
    OFFICE REPORT, ADVENTURE, GENERAL INTELLIGENCE REPORT, in that order
    (`SE3__T2.K2` itself has no Emperor yet -- see the Phase 561 paragraph
    below for the Emperor-elected reordering, sourced from the report's
    own pseudocode rather than a real sample, since no available sample
    has an Emperor).
    `REPORTS.PAS`'s own driver that calls these eleven sections in sequence
    lived in the missing main program -- the same "the caller is lost, not
    the callees" situation as `turn/movement.py`'s hex adjacency scheme --
    so this real generated-output cross-reference is the sourced evidence
    used here, in place of the lost driver.

    **STATE OF THE NATION (Phase 561)**: a real section this composer never
    emitted at all before now -- fixed header + one fixed flavor paragraph,
    always present (unlike ALIGNMENT REDUCTION/FINAL STANDINGS below, this
    one needs no Emperor-election gate of its own), immediately before
    DIPLOMACY. See `describe_state_of_the_nation_report()`'s own docstring.
    **Also Phase 561**: IMPERIAL OFFICE REPORT's own position now depends
    on `state.emperor_kingdom_id` -- before STATE OF THE NATION once an
    Emperor exists (`AKGEN_reverse_engineering_report (5).md` SS29.1/
    SS86.2's own `IF emp < No_King THEN Pray_Report(kng,true)`, called
    inside the real `Desc_Lands` before its own "STATE OF THE NATION:"
    header), still after ARMIES otherwise -- its own *content* already
    correctly differed pre/post-election (`describe_imperial_office_
    report()`'s own docstring); only its position was wrong before this
    phase.

    **All 10 real sections were wired here as of Phase 231** (STATE OF THE
    NATION makes 11, Phase 561) -- ACTION REPORT, LETTER REPORTS, STATE OF
    THE NATION, DIPLOMACY, FINANCES, PROVINCES, CHARACTERS, ARMIES,
    IMPERIAL OFFICE REPORT, ADVENTURE, and GENERAL INTELLIGENCE REPORT.
    "Wired" doesn't mean "complete" -- several sections still
    only render a real subset of their own real content, confirmed
    absent rather than merely unwired:
    - FINANCES itself is only partially wired -- see
      `describe_finances_report()`'s own docstring for exactly which
      of its real lines render (`"Gold in treasury"`/`"Expected
      Revenues"`) and which are confirmed absent (`ACost`/`LCost`-derived
      figures, per-kingdom Discovery tracking).
    - PROVINCES itself is only partially wired -- see `describe_
      provinces_report()`'s own docstring for exactly which columns
      render (name, race, terrain, percent explored; as of Phase 278,
      Tax/Recruiting Types once a `GameState` has been bridged from a
      real `GW3` world file; as of Phase 282/283, the `pt2`-derived
      "(Sea)" parenthetical, project-original rather than sourced -- see that
      docstring's own Phase 282 section) and which is still confirmed
      absent (only the tax-tier grouping presentation now).
    - The real ASCII map (Phase 562) is now wired too -- `describe_
      map_report()` below, appended directly after PROVINCES (the real
      map has no section header of its own; see that function's own
      docstring and `report/ascii_map.py`'s module docstring for the
      full, sourced derivation and exactly which real cases this phase
      does and doesn't reproduce -- notably not name-wrapping, multiple
      maps, or region labels).
    - CHARACTERS itself is only partially wired -- see
      `describe_characters_report()`'s own docstring for exactly which
      fields render (name, location, Alignment, Temperament, Race, Pay
      as of Phase 280, and 15-ability skill levels for a kingdom's own
      leaders only) and which are still confirmed absent (gender,
      Discovery-based skill modifiers, magic-item ownership marks, the
      real procedure's wandering-Hero/Priest-clairvoyance passes).
    - IMPERIAL OFFICE REPORT (Phase 230) renders between ARMIES and
      ADVENTURE, matching the real order -- see `describe_imperial_
      office_report()`'s own docstring for exactly which Merit Point
      terms are fully live today versus still waiting on a future
      battle/encounter/cast wiring phase.
    - GENERAL INTELLIGENCE REPORT (Phase 231) only ever has battle-result
      entries to show -- see `describe_general_intelligence_report()`'s
      own docstring for the confirmed-real event types (movement,
      plagues, terrain illusions, cast spells...) still deferred, and
      `record_battle_world_events()`'s docstring for why this composer
      needs that separate function called once per turn *before* this
      one -- `state.world_events` isn't populated by anything in this
      function's own call chain.

    **Phase 275 -- closing audit for six report identifiers' own Pascal
    *declarations* (not their data).** A fresh, systematic re-check (not
    a re-read of old docstrings) was run against the full surviving
    Pascal archive -- all 14 raw `.PAS` files under `HostAK/TP`/`HostAK/
    MS` (13 with real content; `COMPANY.PAS` is a 5-byte stub) --
    specifically searching for a `function`/`procedure` *declaration* of
    each of `ACost`, `LCost`, `Qual_Modfr`, and `Mod_PAT`, and a `var`/
    array *declaration* of `ptax`/`pt2`. Zero matches for any of the six:
    every real occurrence in `REPORTS.PAS`/`RUMORS.PAS` only ever *calls*
    or *reads* them, confirming (not merely repeating the prior
    inference) that all six live exclusively in the missing main
    turn-processor / the lost `AKGEN.EXE` world-generator -- the same
    "the caller (or, for `ptax`/`pt2`, the writer) is lost, not every
    reader" situation this module's own docstring already established
    for the ten-section driver above. **This finding still stands
    unchanged for all six identifiers** -- no Pascal formula for any of
    them has since turned up.

    **What has changed since (Phases 276/278/279): a missing *formula*
    isn't the same as missing *data*.** Five of these six identifiers
    turned out to be recoverable a different way -- real per-instance
    values sourced from elsewhere in this project rather than re-derived
    from a lost formula, the same "world-gen-only data, not a runtime
    computation" category `name`/`pname` itself closed back in Phase
    150:
    - `ACost`/`LCost` (Phase 276): `describe_finances_report()`'s own
      "Expected Expenses" gap, closed by reusing `ArmyTypeStats.pay`
      and this project's own `hire_pay.py required_pay()` -- see that
      composer's own Phase 276 docstring note.
    - `ptax`/`Mod_PAT` (Phase 278): `describe_provinces_report()`'s own
      Tax-column and Recruiting-Types-columns gaps, closed by
      `parser/gw_world.py`/`gw_world_bridge.py`'s real `GW3` world-file
      decode -- see that composer's own Phase 278 docstring note and
      `gw_world.py`'s own "Recruiting Types (Mod_PAT)" section.
    - `Qual_Modfr` (Phase 279): `describe_armies_report()`'s own
      "Modified Quality" column gap, closed not by one recovered source
      but by recognizing that all five of its real modifiers (home
      province, desert-without-camels, Druidic shortfall, two more from
      the user's own quoted rulebook text) were already sourced,
      already-implemented rulebook mechanics scattered across `turn/
      strength.py`/`turn/battle_orchestrator.py` -- see `turn/army_
      quality.py`'s own docstring for the full derivation.

    **`pt2` (Phase 282) is a different kind of closure from the five
    above -- project-original, not recovered.** `describe_provinces_
    report()`'s own Island parenthetical gap (distinct from `Mod_PAT`,
    despite sharing the old audit bullet -- `turn/recruit.py`'s own
    module docstring cross-references the same underlying "which exactly
    two `ArmyType`s" question `Mod_PAT` used to leave open) still has no
    real Pascal formula AND no real-file data source of any kind --
    unlike `ptax`/`Mod_PAT`/`ACost`/`LCost`, no `GW3` world file (or
    similar) has ever shown a matching pattern, and unlike `Qual_Modfr`,
    no cluster of already-sourced mechanics existed to recognize. What
    renders now is a project-original Island-province system,
    implemented per the user's own explicit domain knowledge
    (2026-07-29, an optional Super AK variant rule for games up to 24
    players) -- the same kind of deliberate, user-confirmed design
    choice `turn/tax_base.py compute_tax_base()` made for `Tax_Base`
    itself, not a continuation of this search. See `models/game_state.py
    ProvinceState.is_island`, `turn/strength.py compute_effective_
    strength()`'s own `is_island` parameter, and `turn/island_provinces.py`
    for the full implementation.

    A related item, the FINANCES "(Including +5 Black Knights)"/
    "(Including +10 Thieves Guild)" notes (`titchar[Evilking]`/
    `LKing(titchar[ThiefPrince])`, `REPORTS.PAS` lines 303-304/316-317),
    had a different shape from the start: the *identifiers* themselves
    (`Evilking`, `ThiefPrince`) are real `models/office.py Office`
    members with real perk text, not missing declarations -- what was
    confirmed absent was a hook tracking a running per-kingdom gold
    total tied to holding either office. Phase 277 closed this with a
    project-original `MeritTally`-sourced formula (the user's own
    supplied reference text, not a recovered Pascal source) -- see
    `merit_points.py`'s own King of Pain/Prince of Thieves docstring
    sections.

    **ALIGNMENT REDUCTION (Phase 229, appended after ADVENTURE)** is
    *not* one of the ten real sections above -- it's a project-original
    presentation of a real, sourced sub-computation (rulebook [10.2]'s
    Alignment-distance Victory Point reduction, `turn/emperor_election.py
    alignment_victory_point_reduction_percent()`, unified with `turn/
    victory_points.py`'s own identical real formula in Phase 558) the
    real engine only ever bakes into each King's own row of the Final
    Standings table below, never as its own separate section. See
    `describe_alignment_victory_point_reduction()`'s own docstring.
    Empty (and therefore omitted, the same convention every other
    section here uses) until `GameState.emperor_kingdom_id` is set.

    **FINAL STANDINGS (Phase 559, appended after ALIGNMENT REDUCTION)**
    is also *not* one of the ten real sections -- same category as
    ALIGNMENT REDUCTION above: a project-original presentation of real,
    previously-computed-but-never-printed data (`turn/final_standings.py
    compose_final_standings_report()`, Phase 454-476, whose own docstring
    explicitly flagged rendering this into report prose as "deliberately
    not attempted" until now). See `describe_final_standings_report()`'s
    own docstring. Empty until an Emperor is elected, same as ALIGNMENT
    REDUCTION.

    **ACTION REPORT** wraps `describe_turn_results()`, filtered here to
    only the King's own `PhaseDispatchResult` entries -- **narrowed as
    of Phase 217**, from every leader in the kingdom down to just the
    King, once `describe_letter_reports()`'s own research confirmed the
    real `Basic_Report()`/`Tell_Story(kng,kng)` only ever narrates the
    King's own turn; every *other* leader's turn belongs in their own
    LETTER REPORTS entry instead (see that composer's own docstring).
    Kingdoms with no `is_king`-flagged leader recorded get no ACTION
    REPORT at all, rather than falling back to the old kingdom-wide
    scope -- the real section is always about one specific King. Its
    own header is added here, since `describe_turn_results()` returns
    bare narrative lines with none.

    **LETTER REPORTS** wraps `describe_letter_reports()` (Phase 217) as-is
    -- it already returns its own `"LETTER REPORTS"` header, so no header
    is added here. Reuses the same `kingdom_results` (every leader in the
    kingdom, King included) rather than `king_results`, since
    `describe_letter_reports()` does its own per-other-leader filtering
    internally.

    **DIPLOMACY**, **FINANCES**, **PROVINCES**, **CHARACTERS**,
    **ARMIES**, **IMPERIAL OFFICE REPORT**, and **ADVENTURE** wrap
    `describe_diplomacy_report()` (Phase 218)/`describe_finances_report()`
    (Phase 219)/`describe_provinces_report()` (Phase 220)/
    `describe_characters_report()` (Phase 221)/`describe_armies_report()`/
    `describe_imperial_office_report()` (Phase 230)/
    `describe_adventure_report()` as-is -- all seven composers already
    return their own header as their first line (the same Phase ~158
    convention Phase 216/218/219/220/221's own composers reuse), so no
    header is added here for any of them; adding one would duplicate it.
    **Phase 440**: `describe_imperial_office_report()` now takes this
    same `kingdom_id` too -- the real procedure's own report is
    genuinely per-Kingdom (see that composer's own docstring for the
    full derivation: pre-election "Best Hope" vs. post-election true
    global winner, always alongside this Kingdom's own runner-up).

    **GENERAL INTELLIGENCE REPORT** (Phase 231, extended Phases 232/234)
    wraps `describe_general_intelligence_report()` as-is, same
    no-extra-header convention as the others -- but unlike every other
    section here, it depends on `record_battle_world_events()`/
    `record_spell_world_events()`/`record_plague_spread_world_events()`
    having already been called once for this whole turn (not per-King)
    before `compose_letter_report()` runs for *any* King; see those
    functions' own docstrings for why.

    A section is omitted entirely from the output when its own composer
    has nothing to say (`describe_turn_results()` returns an empty list
    for a kingdom with no dispatched phases) rather than emitting a
    header with no body -- the same convention `describe_turn_results()`
    itself already uses for individual phase entries.

    **`board_width` (Phase 248)**: forwarded to both `describe_turn_
    results()` (ACTION REPORT) and `describe_letter_reports()` (LETTER
    REPORTS) -- `None` by default, so a full end-to-end letter report
    still narrates zero rumors unless the caller opts in, matching
    every pre-Phase-248 caller's exact existing output.

    **Blank-line spacing (Phase 431)**: the real source's own universal
    idiom, confirmed directly in `REPORTS.PAS`/`YAK.PAS` -- every section
    opens with `PR2` (two blank lines) before its header, and `Expand_
    Write` (the shared header-printing routine) never emits its own
    trailing blank line, so every caller adds exactly one `PR1` (one
    blank line) right after the header itself. Both of those rules are
    universal regardless of what's inside a given section, so they're
    applied here, at the stitching layer, via `_emit_section()` --
    `""` list entries are blank lines once a caller joins this
    function's return value with `"\n"`. The real source's *other* `PR1`
    calls (one after each individual narrative paragraph, e.g. DIPLOMACY
    has three separate "My lord, the following Kings..." paragraphs,
    each needing its own trailing blank line before that paragraph's own
    data) are **not** attempted here -- that needs each composer to
    restructure its own body, not just this stitching function, and is
    deferred to the section-specific phases that will rewrite each
    composer's own fixed-width layout (432-435 per the project plan).
    """

    lines: list[str] = []

    def _emit_section(header: str, body: list[str]) -> None:
        if not body:
            return
        if lines:
            lines.append("")
            lines.append("")
        lines.append(header)
        lines.append("")
        lines.extend(body)

    # Phase 614: state.dead_leaders is included too -- state.leaders
    # alone silently drops a leader who died from their own action this
    # turn (run_turn() already mutated state, including every real
    # remove_leader() call, before compose_letter_report() ever runs),
    # dropping their entire ACTION REPORT/LETTER REPORTS entry, not just
    # the death itself. remove_leader() never touches .kingdom_id on the
    # archived LeaderState, so this is a free, non-inventive lookup, the
    # same shape as _leader_name()'s own Phase 612 fallback -- which
    # this bug had been silently masking downstream of, since that
    # fix's own tests called describe_turn_results() directly, never
    # through this earlier filtering step.
    kingdom_leader_ids = {
        leader.leader_id
        for leader in (*state.leaders.values(), *state.dead_leaders.values())
        if leader.kingdom_id == kingdom_id
    }
    kingdom_results = [entry for entry in results if entry.leader_id in kingdom_leader_ids]

    king_leader_id = _king_leader_id(state, kingdom_id)
    king_results = [entry for entry in kingdom_results if entry.leader_id == king_leader_id]
    action_lines = describe_turn_results(king_results, state, rng, ability_names=ability_names, board_width=board_width)
    _emit_section("ACTION REPORT", action_lines)

    letter_lines = describe_letter_reports(
        kingdom_results, state, kingdom_id, rng, ability_names=ability_names, board_width=board_width
    )
    if letter_lines:
        _emit_section(letter_lines[0], letter_lines[1:])

    # Phase 561: IMPERIAL OFFICE REPORT moves to print here, before
    # STATE OF THE NATION, once an Emperor is elected -- the real
    # `IF emp < No_King THEN Pray_Report(kng,true)` call inside
    # `Desc_Lands`, before its own "STATE OF THE NATION:" header (see
    # describe_state_of_the_nation_report()'s own module-level comment).
    # Without an Emperor it stays in its usual place after ARMIES,
    # unchanged from before this phase.
    imperial_office_lines = describe_imperial_office_report(state, kingdom_id)
    if state.emperor_kingdom_id is not None and imperial_office_lines:
        _emit_section(imperial_office_lines[0], imperial_office_lines[1:])

    state_of_the_nation_lines = describe_state_of_the_nation_report()
    _emit_section(state_of_the_nation_lines[0], state_of_the_nation_lines[1:])

    diplomacy_lines = describe_diplomacy_report(state, kingdom_id)
    if diplomacy_lines:
        _emit_section(diplomacy_lines[0], diplomacy_lines[1:])

    finances_lines = describe_finances_report(state, kingdom_id)
    if finances_lines:
        _emit_section(finances_lines[0], finances_lines[1:])

    provinces_lines = describe_provinces_report(state, kingdom_id)
    if provinces_lines:
        _emit_section(provinces_lines[0], provinces_lines[1:])

    # Phase 562: the real map has no header of its own -- a direct
    # continuation of PROVINCES (see describe_map_report()'s own
    # docstring), so it's appended directly rather than through
    # _emit_section().
    if lines:
        lines.extend(describe_map_report(state, kingdom_id))

    characters_lines = describe_characters_report(state, kingdom_id)
    if characters_lines:
        _emit_section(characters_lines[0], characters_lines[1:])

    armies_lines = describe_armies_report(state, kingdom_id)
    if armies_lines:
        _emit_section(armies_lines[0], armies_lines[1:])

    # Phase 561: only reached here (its old, still-correct position)
    # when there's no Emperor yet -- see the earlier, pre-STATE-OF-THE-
    # NATION call site above for the post-election case.
    if state.emperor_kingdom_id is None and imperial_office_lines:
        _emit_section(imperial_office_lines[0], imperial_office_lines[1:])

    adventure_lines = describe_adventure_report(state, kingdom_id, rng)
    if adventure_lines:
        _emit_section(adventure_lines[0], adventure_lines[1:])

    general_intelligence_lines = describe_general_intelligence_report(state, kingdom_id)
    if general_intelligence_lines:
        _emit_section(general_intelligence_lines[0], general_intelligence_lines[1:])

    alignment_reduction_lines = describe_alignment_victory_point_reduction(state)
    if alignment_reduction_lines:
        _emit_section(alignment_reduction_lines[0], alignment_reduction_lines[1:])

    final_standings_lines = describe_final_standings_report(state)
    if final_standings_lines:
        _emit_section(final_standings_lines[0], final_standings_lines[1:])

    return lines
