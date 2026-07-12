"""Prose micro-template rendering (Phase 58) -- the foundation for report generation.

Reconstructs the *rendering engine* behind the original game's narrative
turn reports (rulebook-adjacent: `HostAK/TP/SAY.PAS`/`RUMORS.PAS`, the
`HostAK/TP/PROSE/*.X2` template files, and `HostAK/TP/PROSE/PROSE.TXT`,
which documents the template mini-language in full for translators).
This module does **not** know anything about `GameState` or what a
report should say -- it only knows how to render one already-selected
template string given a dict of substitution values, the same
separation of concerns ``turn/encounter.py`` (Phase 48) established for
combat before any of its consumers existed.

**`PROSE.TXT` quoted in full for the symbols this module implements**
(the file documents many more -- see "Explicitly out of scope" below
for what's deferred and why):

    _: space character
    {, }: Anything between these symbols has a 50% chance of being
    included in the turn report. They can't be nested.
    /R: The "/R" symbol divides two possible word choices. The program
    will pick one or the other, not both. The "_" character is a means
    of extending a word choice into a phrase.
    /S: The "/S" symbol divides between two possible choices. The left
    choice is used in a land situation, the right choice is for a sea
    or underwater situation.
    ^A (): Either "a" or "an", depending on whether the next word
    begins with a vowel or a consonant.
    ^L (): Causes program to insert list of something. For example,
    "^L=", where "=" means "army", would cause the program to say
    something like "241st Axemen, 34th Legion and 145th Fleet".
    @: Province name; =: Army name; #: A number; \\: Magic Item;
    +: Monster name; *: Direction; `` ` ``: Terrain; ~: Spell name;
    &: Feature name; ^: Ability name; |: Army type name.

**The `/R` and `{...}` resolution order is confirmed from the actual
Pascal engine**, not guessed from the prose alone: ``RUMORS.PAS
Say_Options`` resolves every `/` choice first (a `REPEAT...UNTIL
slashp = 0` loop), *then* every `{...}` block, and only afterward does
the rest of the pipeline convert `_` to a literal space -- word-boundary
scanning for `/R` deliberately treats an underscore-joined phrase like
"bored_with" as a single word (Pascal's own `Stop_Punct` check never
treats `_` as a boundary), which only works if the underscores are
still literal at that point. `render()` reproduces this exact staged
order: resolve `/R` -> resolve `{...}` -> convert `_` to space ->
substitute caller-supplied placeholder values -> resolve `^A`.

**`/R`'s word-boundary scan uses an approximated stop-character set**:
Pascal's own boundary test is `Stop_Punct(c) OR End_Punct(c)`; this
project has `Stop_Punct`'s definition (space, `{`, `}`, `,`) directly
from `Say_Options`, but `End_Punct` itself is defined in `DEFINES.TPU`,
a *compiled* unit with no source in the available Pascal archive.
`_STOP_CHARACTERS` approximates it with the standard set of
sentence-ending/separating punctuation (`.`, `!`, `?`, `:`, `;`) -- a
documented, reasonable guess, not a sourced fact, flagged here as the
first place to revisit if real templates ever render with a word
boundary in the wrong place.

**`/S` (Phase 74)**: quoted in full above -- "The left choice is used
in a land situation, the right choice is for a sea or underwater
situation." Unlike `/R`, this is never random at the Pascal level; it
reads a caller-supplied fact (whether the current province's terrain
is Sea), not a dice roll. `render()`'s new `is_sea` keyword-only
parameter (default ``False``, so every pre-existing caller keeps its
land-side behavior unchanged) drives it -- `/S` shares `/R`'s own
word-boundary-scanning split logic, only the left-vs-right decision
rule differs (`is_sea` directly, instead of a coin flip).

**`/F` (Phase 76)**: PROSE.TXT's own one-line gloss -- "Basically, the
same as '/R', with a different method of random decision" -- undersells
it: like `/S`, it's not random at the Pascal level at all. Confirmed
directly from `RUMORS.PAS Say_Options`'s own `Left_Choice` function,
which is the single shared decision point for **every** `/X` marker
(`'R'`, `'S'`, `'F'`, and `'P'`, all one `CASE` statement): ``'F':
Left_Choice:= boolean(_feat1 and 1)`` -- the left choice is picked
exactly when the current feature instance's own id (`_feat1`, the same
`fn` this project's `models/feature.py Feature.feature_id` already
models) is odd. This is the exact mechanism Phase 75's own research
flagged as "confirmed but not yet implemented," now confirmed a second
time directly against `Say_Options` itself (Phase 75 had only traced
the *equivalent* hand-rolled parity check in `REPORTS.PAS`'s feature-
report code, `IF fn and 1 = 1 THEN ... ELSE ...`, a separate piece of
code that reimplements the same left/right decision by hand on a raw
`mfname[fmagfeat]` string rather than routing through `Say_Options`).
`render()`'s new `feature_id: int | None = None` keyword-only parameter
drives it, mirroring `is_sea`'s shape -- except **`/F` has no safe
default**: unlike land-vs-sea (where "land" is a meaningful default
choice), there is no non-arbitrary parity to assume for "no feature in
context," so a template containing `/F` with no `feature_id` supplied
raises `ValueError` naming the template, rather than silently picking a
side. **No real template in the available archive actually contains a
literal `/F`** (checked all 163 files under `HostAK/TP/PROSE/`, including
every feature-adjacent one -- `FPDESC.X2`, `FSPEC.X2`, `FSEARCH.X`,
`FRUMOR.X`, `MAGFEAT.X2`, `MONSTERS.X2`, `ENCSPEC.X2`) -- unlike `/S`,
which Phase 74 found live in already-transcribed real battle templates,
`/F` is implemented here purely because it's a confirmed, sourced part
of the shared `Say_Options` marker engine, not because a real consumer
needs it yet; `report/turn_report.py` isn't touched this phase.

**`^L` list insertion (Phase 118)**: confirmed content this project had
already found and deliberately left blocked twice (Phase 115's
`_LSLeads`/`_LSGarr`, Phase 117's `_LInher` `THEN` branch and `_MGain`)
-- real templates containing `^L` immediately followed by *another*
marker (`^L^V`, `^L\\`), naming which kind of list to insert (`^V` =
Army name, `\\` = Magic Item, per the symbols this module already
substitutes). `render()`'s new `lists: dict[str, Sequence[str]] | None
= None` keyword-only parameter maps that *following* marker's literal
text to the caller-supplied sequence of strings; `^L<marker>` is
replaced with them joined via `PROSE.TXT`'s own quoted conjunction
format -- comma-separated, no comma before the final item, `" and "`
before the last one, exactly matching the quoted example above
("241st Axemen, 34th Legion and 145th Fleet" for 3 items). 1 item
renders bare (no "and"); 2 items join as `"X and Y"`; 0 items raises
`ValueError`, the same "no sensible default" stance `/F`'s own missing
-`feature_id` case already takes, since an empty list was never a real
possibility in the original engine (`RUMORS.PAS`'s own list-building
loop always has at least the calling entity to list). A template
containing `^L<marker>` with no matching `lists` entry also raises,
naming the template -- not silently left as literal `^L` text in the
output. `^L` resolution runs *before* the generic `values` substitution
pass (a `^L<marker>` pair is fully consumed as a unit; the same marker
appearing elsewhere in the template on its own, if any, still resolves
normally via `values`).

**Explicitly still out of scope, each a real symbol `PROSE.TXT`
documents but this module doesn't implement yet**:

- `/P`: reads whether the current sentence is a merged plural list
  (`Left_Choice:= not mlist` in the same `Say_Options` `CASE`) --
  context this project doesn't have a per-render-call source for yet.
  `render()` raises `NotImplementedError` naming the exact marker if a
  template needs one, rather than silently guessing a 50/50 random
  choice for something that was never random in the original engine.
- `<`, `<2`, `[`, `[1`, `>`, `]` (character-reference pronouns) and the
  King-exclusion markers `^B`/`^E`: these need `RUMORS.PAS Set_Person`/
  `Set_Alt`'s full stateful narrator-perspective system (1st/2nd/3rd
  person depending on who's reading, gender-based pronoun choice,
  "already mentioned this character" tracking) -- a genuinely separate,
  larger piece, not attempted here. A caller may still supply literal
  text for these symbols via `values` if it wants a fixed rendering,
  but no pronoun logic is built into this module.
- `^G`, `^U` (recursive invocation of another prose file): both need a
  caller-supplied *list* of prose files/sub-templates to invoke
  recursively, not just a list of strings like `^L` -- a genuinely
  different, larger piece (recursive rendering), not attempted here.
- Every other named symbol (`^K`, `^Q`, `^R`, `^S`, `^T`, `^V`, `^W`,
  `^X`, `^Y`, `^C`, `^D`, `^F`, `^H`, and the `$`-prefixed family) is
  just plain substitution, already covered by `values` -- nothing
  special needs building for those beyond what `render()` already does;
  they're only "unsupported" in the sense that no report-section code
  exists yet to know what value to supply for them.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

_STOP_CHARACTERS = frozenset(" {},.!?:;")
_VOWELS = frozenset("aeiouAEIOU")
_SUPPORTED_CHOICE_MARKERS = frozenset({"R", "S", "F"})


def _is_stop(c: str) -> bool:
    return c in _STOP_CHARACTERS


def _resolve_choice_markers(
    template: str, rng: random.Random, is_sea: bool, feature_id: int | None
) -> str:
    """Resolves every ``word1/Xword2`` choice, left-to-right, repeatedly (matching
    ``Say_Options``'s own ``REPEAT...UNTIL slashp = 0`` loop). Raises for any
    ``/`` marker other than ``R``/``S``/``F`` -- see module docstring.

    ``/R``'s choice is a coin flip; ``/S``'s is ``is_sea`` directly and
    ``/F``'s is ``feature_id``'s parity (both never random at the Pascal
    level -- see module docstring). All three share the exact same
    word-boundary-scanning split, only the left-vs-right decision rule
    differs.
    """

    s = template
    while True:
        slash_pos = s.find("/")
        if slash_pos == -1:
            return s
        marker = s[slash_pos + 1] if slash_pos + 1 < len(s) else ""
        if marker not in _SUPPORTED_CHOICE_MARKERS:
            raise NotImplementedError(
                f"prose choice marker '/{marker}' isn't supported yet (only /R, /S, /F) -- template: {template!r}"
            )

        right_start = slash_pos + 2
        right_end = right_start
        while right_end < len(s) and not _is_stop(s[right_end]):
            right_end += 1

        if marker == "S":
            choose_right = is_sea
        elif marker == "F":
            if feature_id is None:
                raise ValueError(
                    f"prose template needs /F but no feature_id was supplied -- template: {template!r}"
                )
            choose_right = feature_id % 2 == 0
        else:
            choose_right = rng.random() >= 0.5
        if not choose_right:
            s = s[:slash_pos] + s[right_end:]  # left choice: drop "/X<right>"
        else:
            left_start = slash_pos
            while left_start > 0 and not _is_stop(s[left_start - 1]):
                left_start -= 1
            s = s[:left_start] + s[right_start:right_end] + s[right_end:]  # right choice


def _resolve_optional_inclusion(template: str, rng: random.Random) -> str:
    """Resolves every ``{...}`` block: 50% chance of being included, matching
    ``Say_Options``'s own ``Random < 0.5`` exclusion roll (see module docstring
    for why this maps to "include when >= 0.5"). Blocks can't be nested, per
    ``PROSE.TXT`` -- the first unmatched ``}`` found after each ``{`` is treated
    as the block's own end.
    """

    s = template
    while True:
        start = s.find("{")
        if start == -1:
            return s
        end = s.find("}", start)
        if end == -1:
            raise ValueError(f"unmatched '{{' in template: {template!r}")

        include = rng.random() >= 0.5
        if include:
            s = s[:start] + s[start + 1 : end] + s[end + 1 :]
        else:
            s = s[:start] + s[end + 1 :]


def _join_list(items: Sequence[str]) -> str:
    """Joins a list of strings into ``^L``'s own "X, Y and Z" conjunction
    format -- ``PROSE.TXT``'s own quoted example ("241st Axemen, 34th
    Legion and 145th Fleet"): comma-separated, no comma before the
    final item, ``" and "`` before the last one. See module docstring.
    """

    items = list(items)
    if not items:
        raise ValueError("^L list insertion needs at least one item, got an empty list")
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _resolve_list_insertion(template: str, lists: dict[str, Sequence[str]]) -> str:
    """Resolves every ``^L<marker>`` pair (``PROSE.TXT``'s own ``^L``,
    e.g. ``^L=``) by joining the caller-supplied ``lists[<marker>]``
    via ``_join_list``. Longest marker key checked first, matching
    ``_substitute_placeholders``'s own convention. Raises if a
    template needs ``^L`` but no matching ``lists`` entry was supplied
    -- see module docstring.
    """

    if "^L" not in template:
        return template

    keys = sorted(lists.keys(), key=len, reverse=True)
    result: list[str] = []
    i = 0
    while i < len(template):
        if template.startswith("^L", i):
            matched_key = next((key for key in keys if template.startswith(key, i + 2)), None)
            if matched_key is None:
                raise ValueError(
                    f"prose template needs ^L list insertion but no matching list was "
                    f"supplied for the marker after it -- template: {template!r}"
                )
            result.append(_join_list(lists[matched_key]))
            i += 2 + len(matched_key)
        else:
            result.append(template[i])
            i += 1
    return "".join(result)


def _substitute_placeholders(template: str, values: dict[str, str]) -> str:
    """Single left-to-right scan substituting every caller-supplied symbol, longest
    key first so e.g. a 2-character key is never shadowed by a coincidental
    1-character one.
    """

    if not values:
        return template

    keys = sorted(values.keys(), key=len, reverse=True)
    result: list[str] = []
    i = 0
    while i < len(template):
        for key in keys:
            if template.startswith(key, i):
                result.append(values[key])
                i += len(key)
                break
        else:
            result.append(template[i])
            i += 1
    return "".join(result)


def _resolve_indefinite_articles(template: str) -> str:
    """Resolves ``^A`` to "a" or "an" by peeking past any spaces to the next word's
    first letter -- the symbol itself contributes only the article, not the
    following space (the template already has it, e.g. ``"^A dungeon"``).
    """

    result: list[str] = []
    i = 0
    while i < len(template):
        if template.startswith("^A", i):
            j = i + 2
            while j < len(template) and template[j] == " ":
                j += 1
            next_char = template[j] if j < len(template) else ""
            result.append("an" if next_char in _VOWELS else "a")
            i += 2
        else:
            result.append(template[i])
            i += 1
    return "".join(result)


def render(
    template: str,
    values: dict[str, str] | None = None,
    *,
    rng: random.Random | None = None,
    is_sea: bool = False,
    feature_id: int | None = None,
    lists: dict[str, Sequence[str]] | None = None,
) -> str:
    """Renders one already-selected prose template string, per ``PROSE.TXT``'s
    documented mini-language -- see module docstring for exactly which
    symbols are implemented and which are explicitly deferred.

    ``values`` maps literal symbol text (e.g. ``"@"``, ``"="``, ``"^K"``)
    to its substitution string; unrecognized symbols with no matching
    key are left untouched in the output (no strict-mode validation this
    phase -- see module docstring). ``is_sea`` (Phase 74) drives ``/S``
    choices -- whether the current province's terrain is Sea; defaults
    to ``False`` (the land choice), so every pre-Phase-74 caller keeps
    its existing behavior unchanged. ``feature_id`` (Phase 76) drives
    ``/F`` choices -- the current feature instance's own id, whose
    parity picks the side (see module docstring); defaults to ``None``,
    which is fine for every template that doesn't use ``/F`` but raises
    if one does. ``lists`` (Phase 118) drives ``^L<marker>`` list
    insertion -- maps the marker following ``^L`` (e.g. ``"^V"``,
    ``"\\\\"``) to the sequence of strings to join (see module
    docstring); defaults to ``None``, fine for every template that
    doesn't use ``^L`` but raises if one does.
    """

    rng = rng if rng is not None else random.Random()
    s = _resolve_choice_markers(template, rng, is_sea, feature_id)
    s = _resolve_optional_inclusion(s, rng)
    s = s.replace("_", " ")
    s = _resolve_list_insertion(s, lists or {})
    s = _substitute_placeholders(s, values or {})
    s = _resolve_indefinite_articles(s)
    return s
