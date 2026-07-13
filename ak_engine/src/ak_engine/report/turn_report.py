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
  **This project's Pascal archive has no surviving source for the formula
  that produces `bres` itself** (only the case boundaries are confirmed);
  ``margin_bucket()`` derives an analogous margin from
  ``BattleColumnResult.attacker_win_probability`` (the exact 0.0-1.0 value
  ``turn/battle_line.py estimate_win_probability`` already computes for
  that same column) instead of guessing at ``bres``'s own scale -- a
  documented, unsourced bucketing choice, the same convention
  ``turn/aftermath.py``'s constants already established for a rule with no
  numbers in the rulebook.
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

**"Army name"** (rulebook example: "the 231st Bowmen") is never
synthesized here -- there is no ordinal-numbering/naming system anywhere
in this project (`LNAMES.PAS`/`PRNAMES.PAS` territory, a separate,
entirely unbuilt subsystem). Every function below takes caller-supplied
display-name strings for armies/provinces/kingdoms, the same
values-dict pattern ``prose.render()`` itself already uses.

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
perk's own real-game mechanic, even though no `turn/*.py` resolver
executes an assassination attempt yet (the same narrative-precedes
-execution stance already taken for the Ice-Suspend cluster, Phase
123, and the unexecuted personal-combat spells in
`turn/cast_execution.py`).

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

This project has no source for what determines success versus
failure -- the caller decides, the same caller-supplied-fact pattern
established throughout (`is_sea`, `weapon`, `_ADishK`/`_ADishF`).

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
    file-dispatched and deliberately left for a future phase that
    extracts `ILLMOVE.X2`.

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
  honestly as the fragment it is (likely closed by `_LRidAns`'s own
  file-dispatched `RANS.X`, immediately below it and keyed by the
  same `_qsubplot`, but this project has no access to that file's
  content to confirm). `render_quest_mockery()`.
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
"""

from __future__ import annotations

import random

from ak_engine.models.magic_feature import MAGIC_FEATURE_NAME, MagicFeature
from ak_engine.report.prose import render
from ak_engine.turn.battle_orchestrator import BattleReport
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult
from ak_engine.turn.plan_dispatch import FireExecutionResult, HireExecutionResult
from ak_engine.turn.practice_execution import MAX_SKILL_LEVEL, PracticeExecutionResult
from ak_engine.turn.trade_execution import TradeExecutionResult

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


# Documented, unsourced bucket width (see module docstring: no surviving
# source for the real "bres" formula, only its -5..+5 case boundaries).
_MARGIN_BUCKET_WIDTH = 0.1


def margin_bucket(attacker_win_probability: float) -> int:
    """Buckets a battle column's win probability into the ``bres``-style
    -5..+5 scale ``SAY.PAS _BRes`` dispatches on. Positive = the attacker
    did well in this column. See module docstring for why the bucket
    *boundaries* are sourced but the input formula is a documented,
    unsourced design choice.
    """

    raw = (attacker_win_probability - 0.5) / _MARGIN_BUCKET_WIDTH
    return max(-5, min(5, round(raw)))


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
    bucket = margin_bucket(column.attacker_win_probability)
    variant = pick_variant(_MARGIN_TEMPLATES[bucket], rng)
    result_clause = render(variant, rng=rng, is_sea=is_sea)
    return f"{opening}{defender_clause} and{result_clause}"


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
    """Renders ASpy's report-opening sentence (SPY.X) -- see module docstring
    for why only this one sentence renders: no sourced template exists
    for the rest of ``turn/aspy_execution.py SpyReport``'s own facts
    (owner, adjacent owners, recruitable types, capital status).
    """

    variant = pick_variant(_SPY_TEMPLATES, rng)
    values = {"<": spy_name, "@": province_name, ">": f"{spy_name}'s", "^B": "", "^E": ""}
    return render(variant, values, rng=rng)


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


def describe_battle(
    battle_report: BattleReport,
    *,
    attacker_name: str,
    defender_name: str,
    province_name: str,
    army_names: dict[int, str],
    destination_names: dict[int, str],
    rng: random.Random,
    is_sea: bool = False,
) -> list[str]:
    """Assembles the full battle-outcome narrative from an already-computed
    ``BattleReport`` (``turn/battle_orchestrator.py fight_battle()``), in
    the same order the original dispatch table produces them: per-column
    clashes, the winner sentence, destroyed armies, pursuit kills, then
    retreats.

    ``army_names``/``destination_names`` map army ids (``BattleReport``'s
    own id lists, and each column's ``BattleUnit.source_id``) to
    caller-supplied display strings -- see module docstring: no army- or
    province-naming system exists in this project yet, so nothing here is
    synthesized. ``is_sea`` (Phase 74) is the caller-known fact of
    whether ``province_name`` is a Sea province, threaded to every
    sub-renderer whose own templates carry a "/S" marker.

    A battle column whose front unit(s) have no entry in ``army_names``
    (a garrison/mercenary/unled stack this project's caller chose not to
    name) is skipped for the per-column clash sentence -- not guessed.
    """

    lines: list[str] = []

    for column in battle_report.battle_result.columns:
        if not column.attacker_units or not column.defender_units:
            continue
        attacker_army_name = army_names.get(column.attacker_units[0].source_id)
        defender_army_name = army_names.get(column.defender_units[0].source_id)
        if attacker_army_name is None or defender_army_name is None:
            continue
        lines.append(render_column_clash(column, attacker_army_name, defender_army_name, rng, is_sea=is_sea))

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

    Only ``render_hire_accepted`` (``ACCHIRE.X``) is ever reachable:
    ``_dispatch_hire()``'s own docstring already documents that this
    project always charges the full offer and always accepts a Hire
    that's co-located and affordable ("Simplification: the rulebook's
    Hero 'pay required'... isn't modeled"), so neither
    ``render_hire_refused`` (``REFHIRE.X``, alignment-based) nor
    ``render_hire_counter_offer`` (``_LCounter``, price-based) has any
    real trigger in ``HireExecutionResult.reason`` -- every one of its
    real failure strings ("hero not found", "cannot hire a King", "hero
    already in service", "not co-located", "insufficient treasury") is
    an administrative failure with no sourced narrative template,
    exactly like most of ``describe_give()``'s own failure reasons.
    """

    if result.hired:
        return render_hire_accepted(character_name, hireling_name, king_name, rng)
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

    Only two of this project's Practice renderers are ever reachable,
    and both need information ``PracticeExecutionResult`` alone doesn't
    carry, matching ``describe_battle()``'s own caller-supplies-names
    convention:

    - ``render_practice_already_maxed`` (``_LAlrMax``) fires when the
      attempt started at ``MAX_SKILL_LEVEL`` (9, ``CTBOTH.PAS``'s own
      ``skillrange`` ceiling): ``attempt_skill_rise()`` short-circuits
      to ``skill_rose=False`` with ``new_skill`` unchanged in that case,
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
    - Every other case (a normal failed roll, an aptitude-only rise,
      ``not_implemented_for_ability``) has no sourced narrative and
      renders nothing.
    """

    if result.new_skill == MAX_SKILL_LEVEL and not result.skill_rose:
        return render_practice_already_maxed(character_name, ability_name, rng)
    if result.skill_rose and teacher_name is not None:
        return render_practice_tutored(character_name, ability_name, teacher_name, rng)
    return None


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
      ``_LTrade`` -- needs a caller-supplied ``item_name`` (this project
      has no item-instance display-name synthesis, the same
      caller-supplies-names convention ``describe_battle()``'s own
      ``army_names`` already uses); returns ``None`` without one rather
      than guessing.
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
