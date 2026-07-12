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
  owners / recruitable types / capital" sentences themselves. No
  dedicated PROSE template for those specific facts turned up anywhere
  in the available Pascal source (`SPDESC.X2`/`FPDESC.X2` are Search
  Feature-power descriptions, unrelated despite the similar name).
  Rendering the rest of `turn/aspy_execution.py SpyReport` stays
  explicitly open, the same category of gap as Hide_Feature/
  Clairvoyance -- not force-composed from invented, unsourced prose.
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
"""

from __future__ import annotations

import random

from ak_engine.models.magic_feature import MAGIC_FEATURE_NAME, MagicFeature
from ak_engine.report.prose import render
from ak_engine.turn.battle_orchestrator import BattleReport
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult

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
