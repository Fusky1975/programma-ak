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
  supplies. Only 2 of CONQ.X's real 4 variants are used -- the other
  two need the "/S" (Sea-terrain) marker `report/prose.py` deliberately
  doesn't resolve, and this function takes no terrain parameter to
  resolve it with; see `_CONQ_TEMPLATES`'s own comment.
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
"""

from __future__ import annotations

import random

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

# HostAK/TP/PROSE/CONQ.X -- Move conquering an undefended province. Only 2
# of the real file's 4 variants are usable here: the other two ("armies/S
# naval_forces", "host/Sfleet") use the "/S" marker (Sea-terrain
# conditional), which report/prose.py deliberately doesn't resolve --
# render_uncontested_conquest() has no is_sea_province parameter to
# resolve it with, and guessing would silently pick the wrong branch on a
# real Sea conquest. Left out rather than guessed; a future extension
# that threads terrain through can restore both.
_CONQ_TEMPLATES: list[str] = [
    "<'s forces conquered/Rtook @ without any major battles/Rengagements.",
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


def render_column_clash(
    column: BattleColumnResult,
    attacker_army_name: str,
    defender_army_name: str,
    rng: random.Random,
) -> str:
    """Renders one battle column's "<army> fought with <army> and <result>"
    sentence (``SAY.PAS _BClash`` + ``_BRes``, rulebook [7.2]'s "number of
    contests equal to the length of the battle line").
    """

    opening = render("= fought/Rbattled {with }", {"=": attacker_army_name}, rng=rng)
    defender_clause = render("=", {"=": defender_army_name}, rng=rng)
    bucket = margin_bucket(column.attacker_win_probability)
    variant = pick_variant(_MARGIN_TEMPLATES[bucket], rng)
    result_clause = render(variant, rng=rng)
    return f"{opening}{defender_clause} and{result_clause}"


def render_battle_winner(
    battle_result: BattleResult,
    attacker_name: str,
    defender_name: str,
    province_name: str,
    rng: random.Random,
) -> str | None:
    """Renders the overall battle-winner sentence (``SAY.PAS _BWinner`` /
    WINNER.X, DEFWIN.X). Returns ``None`` for a tie -- no template exists
    for that outcome anywhere in this project's archive (see module
    docstring).
    """

    if battle_result.winner == "tie":
        return None
    if battle_result.winner == "attacker":
        variant = pick_variant(_WINNER_TEMPLATES, rng)
        values = {"<": attacker_name, "<2": attacker_name, "[": defender_name}
    else:
        variant = pick_variant(_DEFWIN_TEMPLATES, rng)
        values = {"<": attacker_name, "@": province_name}
    return render(variant, values, rng=rng)


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


def render_retreat(retreating_name: str, destination_name: str, rng: random.Random) -> str:
    """Renders a retreat sentence (RETREAT.X). ``>`` (possessive) is rendered
    as a literal ``"<name>'s"`` -- see module docstring: the real
    pronoun/possessive system stays out of scope, same as
    ``report/prose.py``'s own deferred ``<``/``[``/``>`` handling.
    """

    variant = pick_variant(_RETREAT_TEMPLATES, rng)
    values = {"<": retreating_name, "^S": destination_name, ">": f"{retreating_name}'s"}
    return render(variant, values, rng=rng)


def render_uncontested_conquest(attacker_name: str, province_name: str, rng: random.Random) -> str:
    """Renders an undefended-province conquest sentence (CONQ.X) -- a Move
    that takes an enemy province with no battle at all, distinct from
    every other function in this module (which all describe a fought
    ``BattleReport``).
    """

    variant = pick_variant(_CONQ_TEMPLATES, rng)
    return render(variant, {"<": attacker_name, "@": province_name}, rng=rng)


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
    synthesized.

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
        lines.append(render_column_clash(column, attacker_army_name, defender_army_name, rng))

    winner_sentence = render_battle_winner(
        battle_report.battle_result, attacker_name, defender_name, province_name, rng
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
            lines.append(render_retreat(name, destination, rng))

    return lines
