"""Writer for the player move-submission .K1 format -- the exact inverse
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
  Pursue phase's own ``extra``, or a plan's own ``SP:`` tactic list) is
  **not** supported here -- ``tests/test_k1_moves_parser.py``'s own
  docstring confirms no real ``AK3__T*.K1`` sample contains one, and
  writing its on-disk shape back out (free text on its own line(s),
  blank-line-terminated) is exactly the kind of per-command syntax
  decision the user asked to make deliberately, one command at a time,
  rather than guessed at here. ``write_k1_moves_file()`` raises
  ``K1WriteError`` if it ever encounters one, rather than silently
  emitting a file that wouldn't re-parse correctly.
- Every other phase's ``extra`` (plain ``int``s only) round-trips as
  plain whitespace-separated integers -- exactly what
  ``parser/tokens.py consume_ints()`` already expects.

**Verified**: ``tests/test_k1_moves_writer.py`` round-trips all 10 real
``AK3__T*.K1`` samples (parse -> write -> re-parse -> same structure).
"""

from __future__ import annotations

from ak_engine.models.kingdom import Kingdom
from ak_engine.models.plan import ActionPlan, PlanSegment

_BOILERPLATE = (
    "    This moves file contains the moves of your King and his characters.\n"
    " It is read in by the game moderator's computer.  Don't alter anything!\n"
    " If you have any comments, write them at the very bottom of this file.\n"
)


class K1WriteError(ValueError):
    """Raised when a ``Kingdom`` carries a shape this writer doesn't support yet."""


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
        if tokens:
            lines.append(" " + " ".join(tokens))

    lines.append(" 255")
    if kingdom.trailer_comments:
        lines.append(kingdom.trailer_comments)

    return "\n".join(lines) + "\n"


def _plan_tokens(plan: ActionPlan) -> list[str]:
    tokens: list[str] = []
    for segment in plan.segments:
        tokens.extend(_segment_tokens(segment))
    return tokens


def _segment_tokens(segment: PlanSegment) -> list[str]:
    tokens = ["AP:", str(segment.plan_start), str(segment.plan_end)]
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


def _value_token(value: int | str) -> str:
    if isinstance(value, str):
        raise K1WriteError(
            f"a SAY tactic's own free-text argument ({value!r}) isn't supported by this writer yet "
            "-- see this module's own docstring"
        )
    return str(int(value))
