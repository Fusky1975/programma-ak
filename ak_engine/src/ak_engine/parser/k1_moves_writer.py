r"""Writer for the player move-submission .K1 format -- the exact inverse
of ``parser/k1_moves.py``'s ``parse_k1_moves_file()``.

**Why this exists**: the GM webapp's manual "compose moves" editor (and,
later, a player-facing moves UI the user plans to build) both need to
produce a real move file of a King's own orders, not just consume one --
building a ``Kingdom`` in Python and handing it to this module keeps
both producers going through the exact same real syntax the turn
engine already parses, by construction, rather than two independent
guesses at "the same format" drifting apart.

**Line layout doesn't matter, only token order does**: ``parser/
tokens.py flatten_tokens_with_lines()`` whitespace-splits every line and
concatenates them into one flat token stream before any of
``parser/k1_moves.py``'s own grammar runs -- a newline is exactly as
meaningful as a space, *except* for a ``SAY`` tactic's own free-text
argument (see below), which this writer doesn't support. So this module
always emits one leader block per physical line; nothing about the
grammar requires matching the original file's own line breaks.

**Scope, matched to what ``parser/k1_moves.py`` itself confirms is real**:

- A nested Hire/Charm/Resurrection plan (``PlanPhase.nested_plan``) is
  written correctly, recursively -- common in real data (9 of the 10
  ``AK3__T*.K1`` samples use one), so a writer that couldn't round-trip
  it would fail on most real files, not just an edge case.
- A ``SAY`` tactic's own free-text argument (inside a Search/Challenge/
  Pursue phase's own ``extra``, or a plan's own ``SP:`` tactic list) --
  sourced directly from the user (2026-10-27) when designing the
  Encounter Plan's own Say tactic -- is written on its own line right
  after the ``SAY`` ordinal's own line, terminated by a blank line,
  exactly the shape ``parser/k1_moves.py _recover_say_text()`` expects
  (its own docstring: "the text sits on the line(s) immediately after
  the SAY ordinal's own line, terminated by a blank line"). This is
  the one case where this module's own "line layout doesn't matter"
  claim above doesn't hold -- ``_render_leader_lines()`` below breaks
  the leader's own flat token stream into several physical lines
  around every ``_SayText`` marker for exactly this reason, unlike
  every other value (plain integers), which still round-trips fine on
  one flat line regardless of where line breaks fall. A resumption
  line (the one right after a SAY's own blank terminator) that starts
  with a bare positive ordinal immediately followed by a token
  starting with ``-`` (most commonly the tactic list's own ``-1``
  terminator, e.g. a Say then a Melee in the same round) would
  otherwise collide with ``parser/tokens.py match_leader_header()``'s
  own ``^(\d+)\s+-(.+)$`` pattern and get misread as a brand new
  leader block -- ``_render_leader_lines()`` guards against exactly
  this by prefixing such a line's own first token with a harmless
  ``+`` (``int("+9") == 9``, and the ``+`` spelling isn't a digit, so
  the header regex no longer matches at position 0).
- Every other phase's ``extra`` (plain ``int``s) round-trips as plain
  whitespace-separated integers -- exactly what ``parser/tokens.py
  consume_ints()`` already expects.

**Verified**: ``tests/test_k1_moves_writer.py`` round-trips all 10 real
``AK3__T*.K1`` samples (parse -> write -> re-parse -> same structure),
plus hand-built SAY fixtures (no real sample contains one, confirmed by
``tests/test_k1_moves_parser.py``'s own docstring).
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.kingdom import Kingdom
from ak_engine.models.plan import ActionPlan, PlanSegment
from ak_engine.parser.tokens import match_leader_header

_BOILERPLATE = (
    "    This moves file contains the moves of your King and his characters.\n"
    " It is read in by the game moderator's computer.  Don't alter anything!\n"
    " If you have any comments, write them at the very bottom of this file.\n"
)


class K1WriteError(ValueError):
    """Raised when a ``Kingdom`` carries a shape this writer doesn't support yet."""


@dataclass(frozen=True, slots=True)
class _SayText:
    """Marks a SAY tactic's own free-text argument in a leader's flat token
    stream, so ``_render_leader_lines()`` can split that stream onto several
    physical lines around it, instead of folding it in as a plain token."""

    text: str


def write_k1_moves_file(kingdom: Kingdom) -> str:
    """The exact inverse of ``parse_k1_moves_file()``: a real .K1 move
    file's full text, built from ``kingdom``.

    ``kingdom.source_filename`` both names the Kingdom in the "Moves
    for..." line and is where a caller's own ``.K<kingdom_id>`` naming
    convention must already live (this function reads it, never writes
    it to disk itself) -- see ``Kingdom.kingdom_id``'s own docstring.
    """

    lines = [
        _BOILERPLATE.rstrip("\n"),
        "",
        f" Moves for {kingdom.king_name}'s Kingdom ({kingdom.source_filename}):",
        f" {kingdom.header.sex} " + " ".join(str(value) for value in kingdom.header.raw_fields),
        " " + " ".join(str(value) for value in kingdom.skills.raw_values),
        f" {kingdom.king_name}",
    ]
    if kingdom.king_title is not None:
        lines.append(f" {kingdom.king_title}")

    for leader in kingdom.leaders:
        # The leader header ("<id> -<name>") must be its own physical
        # line: `parser/tokens.py match_leader_header()` is checked
        # line-by-line, *before* flattening, unlike everything else in
        # a leader's own body (which is flattened first) -- putting any
        # AP:/P-code tokens on the same line would make the whole rest
        # of that line part of the regex's own greedy name capture.
        lines.append(f" {leader.leader_id} -{leader.name}")
        tokens = _plan_tokens(leader.plan)
        lines.extend(_render_leader_lines(tokens))

    lines.append(" 255")
    if kingdom.trailer_comments:
        lines.append(kingdom.trailer_comments)

    return "\n".join(lines) + "\n"


def _plan_tokens(plan: ActionPlan) -> list[str | _SayText]:
    tokens: list[str | _SayText] = []
    for segment in plan.segments:
        tokens.extend(_segment_tokens(segment))
    return tokens


def _segment_tokens(segment: PlanSegment) -> list[str | _SayText]:
    tokens: list[str | _SayText] = ["AP:", str(segment.plan_start), str(segment.plan_end)]
    if segment.sp:
        tokens.append("SP:")
        tokens.extend(_value_token(value) for value in segment.sp)

    for label_num in range(segment.plan_start, segment.plan_end + 1):
        label = f"P{label_num}"
        phase = segment.phases.get(label)
        if phase is None:
            raise K1WriteError(
                f"segment is missing phase {label!r} (plan_start={segment.plan_start}, plan_end={segment.plan_end})"
            )
        tokens.append(label)
        tokens.append(":")
        tokens.append(_value_token(phase.action))
        tokens.append(_value_token(phase.obj))
        tokens.extend(_value_token(value) for value in phase.extra)

        if phase.nested_plan is not None:
            if label_num >= 4:
                raise K1WriteError(f"phase {label!r} carries a nested_plan, but only P0-P3 can (see PlanPhase's own docstring)")
            nested_tokens = _plan_tokens(phase.nested_plan)
            if not nested_tokens:
                raise K1WriteError(f"phase {label!r}'s own nested_plan has no segments to write")
            tokens.extend(nested_tokens)

    return tokens


def _value_token(value: int | str) -> str | _SayText:
    if isinstance(value, str):
        return _SayText(value)
    return str(int(value))


def _render_leader_lines(tokens: list[str | _SayText]) -> list[str]:
    """Splits a leader's own flat token stream into physical lines, matching
    ``parser/k1_moves.py _recover_say_text()``'s own requirement: a SAY
    tactic's free text sits on the line right after the SAY ordinal's own
    line, terminated by a blank line. Every other token is line-break-
    agnostic (see this module's own docstring), so they're all folded onto
    one line together, right up to (and including) the SAY ordinal itself;
    whatever follows a SAY text resumes on a fresh line of its own."""

    lines: list[str] = []
    current: list[str] = []
    for token in tokens:
        if isinstance(token, _SayText):
            lines.append(_render_line(current))
            current = []
            lines.append(f" {token.text}")
            lines.append("")
        else:
            current.append(token)
    if current:
        lines.append(_render_line(current))
    return lines


def _render_line(tokens: list[str]) -> str:
    line = " " + " ".join(tokens)
    if match_leader_header(line) is not None:
        tokens = [f"+{tokens[0]}", *tokens[1:]]
        line = " " + " ".join(tokens)
    return line
