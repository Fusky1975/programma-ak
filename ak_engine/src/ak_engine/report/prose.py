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

**Explicitly still out of scope, each a real symbol `PROSE.TXT`
documents but this module doesn't implement yet**:

- `/F`, `/P`: neither is random at the Pascal level either -- `/F`
  reads a feature-instance parity bit (`_feat1`) and `/P` reads
  whether the current sentence is a merged plural list -- context this
  project doesn't have a per-render-call source for yet. `render()`
  raises `NotImplementedError` naming the exact marker if a template
  needs one, rather than silently guessing a 50/50 random choice for
  something that was never random in the original engine.
- `<`, `<2`, `[`, `[1`, `>`, `]` (character-reference pronouns) and the
  King-exclusion markers `^B`/`^E`: these need `RUMORS.PAS Set_Person`/
  `Set_Alt`'s full stateful narrator-perspective system (1st/2nd/3rd
  person depending on who's reading, gender-based pronoun choice,
  "already mentioned this character" tracking) -- a genuinely separate,
  larger piece, not attempted here. A caller may still supply literal
  text for these symbols via `values` if it wants a fixed rendering,
  but no pronoun logic is built into this module.
- `^G`, `^U` (recursive invocation of another prose file), `^L` (list
  insertion with "X, Y and Z" conjunction formatting): both need a
  caller-supplied *list* of values, not a single string -- a natural,
  small follow-up once a real consumer needs one, not attempted here to
  keep `render()`'s own signature (one string in, one string out) simple
  for this first phase.
- Every other named symbol (`^K`, `^Q`, `^R`, `^S`, `^T`, `^V`, `^W`,
  `^X`, `^Y`, `^C`, `^D`, `^F`, `^H`, and the `$`-prefixed family) is
  just plain substitution, already covered by `values` -- nothing
  special needs building for those beyond what `render()` already does;
  they're only "unsupported" in the sense that no report-section code
  exists yet to know what value to supply for them.
"""

from __future__ import annotations

import random

_STOP_CHARACTERS = frozenset(" {},.!?:;")
_VOWELS = frozenset("aeiouAEIOU")
_SUPPORTED_CHOICE_MARKERS = frozenset({"R", "S"})


def _is_stop(c: str) -> bool:
    return c in _STOP_CHARACTERS


def _resolve_choice_markers(template: str, rng: random.Random, is_sea: bool) -> str:
    """Resolves every ``word1/Xword2`` choice, left-to-right, repeatedly (matching
    ``Say_Options``'s own ``REPEAT...UNTIL slashp = 0`` loop). Raises for any
    ``/`` marker other than ``R``/``S`` -- see module docstring.

    ``/R``'s choice is a coin flip; ``/S``'s is ``is_sea`` directly (never
    random at the Pascal level -- see module docstring). Both share the
    exact same word-boundary-scanning split, only the left-vs-right
    decision rule differs.
    """

    s = template
    while True:
        slash_pos = s.find("/")
        if slash_pos == -1:
            return s
        marker = s[slash_pos + 1] if slash_pos + 1 < len(s) else ""
        if marker not in _SUPPORTED_CHOICE_MARKERS:
            raise NotImplementedError(
                f"prose choice marker '/{marker}' isn't supported yet (only /R, /S) -- template: {template!r}"
            )

        right_start = slash_pos + 2
        right_end = right_start
        while right_end < len(s) and not _is_stop(s[right_end]):
            right_end += 1

        choose_right = is_sea if marker == "S" else rng.random() >= 0.5
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
    its existing behavior unchanged.
    """

    rng = rng if rng is not None else random.Random()
    s = _resolve_choice_markers(template, rng, is_sea)
    s = _resolve_optional_inclusion(s, rng)
    s = s.replace("_", " ")
    s = _substitute_placeholders(s, values or {})
    s = _resolve_indefinite_articles(s)
    return s
