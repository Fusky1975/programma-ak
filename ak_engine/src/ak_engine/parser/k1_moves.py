"""Parser for the player move-submission .K1 format (e.g. AK3__T1.K1).

Not to be confused with the turn-report .K1 files produced by the original
engine (e.g. SE3__T0.K1), which are unrelated narrative text and are not
handled here.

**Phase 618 -- Search's own ``SAY`` tactic**: every phase's ``action``/
``obj``/``extra`` values are ordinarily read by ``consume_ints()`` off
one flat, whitespace-tokenized stream (line boundaries and blank lines
already discarded -- see ``parser/tokens.py flatten_tokens()``). A
Search phase's own ``SAY`` Encounter Plan tactic breaks that model: its
argument is free text on its own line(s), terminated by a blank line
(``turn/search_decode.py``'s own module docstring has the full Pascal
citation and the user's direct confirmation of the on-disk shape).
``_build_leader()`` therefore also keeps ``flatten_tokens_with_lines()``'s
own per-token line map (and the raw ``body_lines``) alongside the flat
token stream, threaded down through every parsing function below, so
that the moment a Search phase's own tactic-list walk (``_consume_
search_extra()``) reaches a ``SAY`` ordinal, it can jump back to the
original lines and recover the text directly (``_recover_say_text()``),
then resynchronize the flat token index past whatever it consumed.
Every other phase/action type is completely unaffected -- see
``_parse_segment()``'s own Phase 618 addendum for exactly where the two
paths split.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

from ak_engine.models.enums import (
    TACTICS_WITH_SUB_OBJECT,
    ActionCode,
    Maneuver,
    Spell,
    action_from_int,
    maneuver_from_int,
)
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader, SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.tokens import consume_ints, flatten_tokens_with_lines, is_keyword, match_leader_header

_MOVES_FOR_RE = re.compile(r"Moves for (.+)'s Kingdom \((.+)\):")
_EXPECTED_SKILL_VALUES = 31  # observed across all AK3__T*.K1 samples; not yet 15 clean pairs


def parse_k1_moves_file(path: Path) -> Kingdom:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if not lines or "moves file" not in lines[0].lower():
        warnings.warn(
            f"{path.name}: first line doesn't look like the expected instructions boilerplate",
            stacklevel=2,
        )

    moves_for_idx = _find_moves_for_line(lines, path)
    header_idx = moves_for_idx + 1
    header = _parse_header_line(lines, header_idx, path)

    skill_idx = header_idx + 1
    skills = _parse_skill_line(lines, skill_idx, path)

    king_name_idx = skill_idx + 1
    king_name = _line_at(lines, king_name_idx, path).strip()

    next_idx = king_name_idx + 1
    next_line = _line_at(lines, next_idx, path)
    if match_leader_header(next_line) is not None:
        king_title: str | None = None
        leader_loop_start = next_idx
    else:
        king_title = next_line.strip()
        leader_loop_start = next_idx + 1

    leaders, trailer_comments = _parse_leader_blocks(lines, leader_loop_start, path)

    return Kingdom(
        source_filename=path.name,
        king_name=king_name,
        king_title=king_title,
        header=header,
        skills=skills,
        leaders=leaders,
        trailer_comments=trailer_comments,
    )


def _line_at(lines: list[str], index: int, path: Path) -> str:
    if index >= len(lines):
        raise K1ParseError(f"{path.name}: unexpected end of file", line_number=index)
    return lines[index]


def _find_moves_for_line(lines: list[str], path: Path) -> int:
    for i, line in enumerate(lines):
        if _MOVES_FOR_RE.search(line):
            return i
    raise K1ParseError(f"{path.name}: no 'Moves for ... Kingdom (...):' line found")


def _parse_header_line(lines: list[str], index: int, path: Path) -> KingdomMoveHeader:
    """Parse the Kingdom-header line.

    The leading token is not a literal ``"M"`` marker (a previous, now-
    corrected assumption -- see ``KingdomMoveHeader``'s own docstring,
    Phase 464): it's ``sex[kng]``, a single-character Pascal ``Char``
    field. Every available sample happens to be a male King (``"M"``),
    which is exactly what made the old literal check look correct.
    """

    line = _line_at(lines, index, path)
    tokens = line.split()
    if not tokens:
        raise K1ParseError("expected kingdom header line", line_number=index, line=line)
    sex = tokens[0]
    if len(sex) != 1:
        raise K1ParseError(
            f"expected a single-character sex field, got {sex!r}", line_number=index, line=line
        )
    try:
        raw_fields = [int(tok) for tok in tokens[1:]]
    except ValueError as exc:
        raise K1ParseError("kingdom header line contains a non-integer field", line_number=index, line=line) from exc
    return KingdomMoveHeader(raw_fields=raw_fields, sex=sex)


def _parse_skill_line(lines: list[str], index: int, path: Path) -> SkillTable:
    line = _line_at(lines, index, path)
    tokens = line.split()
    try:
        raw_values = [int(tok) for tok in tokens]
    except ValueError as exc:
        raise K1ParseError("skill-values line contains a non-integer field", line_number=index, line=line) from exc
    if len(raw_values) != _EXPECTED_SKILL_VALUES:
        raise K1ParseError(
            f"expected {_EXPECTED_SKILL_VALUES} integers on the skill-values line, got {len(raw_values)}",
            line_number=index,
            line=line,
        )
    return SkillTable(raw_values=raw_values)


def _parse_leader_blocks(lines: list[str], start: int, path: Path) -> tuple[list[Leader], str]:
    leaders: list[Leader] = []
    current_id: int | None = None
    current_name: str | None = None
    body_lines: list[str] = []
    sentinel_idx: int | None = None

    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped == "255":
            sentinel_idx = i
            break
        header = match_leader_header(line)
        if header is not None:
            if current_id is not None:
                leaders.append(_build_leader(current_id, current_name, body_lines))
            current_id, current_name = header
            body_lines = []
        elif current_id is not None:
            # Phase 618: blank lines *within* a leader block are kept too
            # (previously dropped here, `elif stripped:`) -- a Search
            # phase's own SAY tactic needs a real blank line to mark
            # where its free text ends (see `_recover_say_text()`).
            # Harmless for every other line: `flatten_tokens_with_lines()`
            # already produces zero tokens for a blank line, so nothing
            # about the flat token stream changes, only the line indices
            # `token_line` reports (never observed outside this phase's
            # own SAY recovery).
            body_lines.append(line)
        elif stripped:
            raise K1ParseError(
                "unexpected content before first leader block",
                line_number=i,
                line=line,
            )
        i += 1

    if sentinel_idx is None:
        raise K1ParseError(f"{path.name}: missing '255' sentinel terminating leader blocks")

    if current_id is not None:
        leaders.append(_build_leader(current_id, current_name, body_lines))

    trailer_comments = "\n".join(lines[sentinel_idx + 1 :]).strip()
    return leaders, trailer_comments


_MAX_NESTED_PLAN_DEPTH = 100


def _build_leader(leader_id: int, name: str | None, body_lines: list[str]) -> Leader:
    tokens, token_line = flatten_tokens_with_lines(body_lines)
    plan, i = _parse_action_plan(
        tokens, 0, leader_id, owner_desc=f"leader {leader_id}", token_line=token_line, lines=body_lines
    )
    if i != len(tokens):
        raise K1ParseError(f"leader {leader_id}: unexpected trailing tokens after plan: {tokens[i:]!r}")

    return Leader(leader_id=leader_id, name=name or "", plan=plan)


def _parse_action_plan(
    tokens: list[str],
    i: int,
    leader_id: int | None,
    *,
    owner_desc: str,
    token_line: list[int],
    lines: list[str],
    depth: int = 0,
) -> tuple[ActionPlan, int]:
    """Parse as many consecutive ``AP:`` segments as appear at ``i``.

    Used both for a leader's own top-level plan and, recursively, for a
    nested Hire/Charm/Resurrection character's embedded plan (see
    ``models/plan.py``'s module docstring) -- the two are structurally
    identical, just entered from a different call site.

    ``token_line``/``lines`` (Phase 618) are threaded through purely so a
    nested plan can also decode a Search phase's own ``SAY`` tactic
    correctly -- see this module's own docstring.

    Bug fix (crash/DoS): ``depth`` caps the ``_parse_segment() ->
    _maybe_parse_nested_plan() -> _parse_action_plan()`` recursion this
    function is part of. A move file with a few thousand consecutive
    ``AP: 0 0 P0 ... AP: 0 0 P0 ...`` segments -- each one's own phase
    immediately followed by another ``AP:``, which is *all* it takes to
    trigger a nested-plan parse regardless of that phase's actual action
    -- used to blow Python's own recursion limit with an unhandled
    ``RecursionError``, uncaught by every one of this parser's own
    callers (which only ever catch ``K1ParseError``/``ValueError``/
    ``IndexError``). No real move file nests anywhere close to this deep
    (Hire/Charm/Resurrection's own embedded-plan nesting is the only real
    trigger, and even that rarely goes more than one or two levels), so
    the cap is purely a safety net, raised as the same kind of clean,
    already-handled parse error every other malformed-input case here
    produces.
    """

    if depth > _MAX_NESTED_PLAN_DEPTH:
        raise K1ParseError(f"{owner_desc}: nested plans are more than {_MAX_NESTED_PLAN_DEPTH} levels deep")

    segments: list[PlanSegment] = []
    while i < len(tokens) and tokens[i] == "AP:":
        segment, i = _parse_segment(tokens, i, owner_desc=owner_desc, token_line=token_line, lines=lines, depth=depth)
        segments.append(segment)
    return ActionPlan(leader_id=leader_id, segments=segments), i


def _parse_segment(
    tokens: list[str], i: int, *, owner_desc: str, token_line: list[int], lines: list[str], depth: int = 0
) -> tuple[PlanSegment, int]:
    """Parse one ``AP: <start> <end> SP: ... P<start>..P<end>`` group.

    Phases are read for exactly the labels in ``range(plan_start,
    plan_end + 1)``, in order -- not "whatever P-keyword comes next" --
    which is what lets this correctly tell a genuinely new sibling
    segment apart from a nested character's plan (see
    ``_maybe_parse_nested_plan``): a mismatch here is a real parse error,
    not silent data loss.
    """

    assert tokens[i] == "AP:"
    values, i = consume_ints(tokens, i + 1)
    if len(values) != 2:
        raise K1ParseError(f"{owner_desc}: 'AP:' expected 2 integers, got {values}")
    plan_start, plan_end = values
    segment = PlanSegment(plan_start=plan_start, plan_end=plan_end, sp=())

    if i < len(tokens) and tokens[i] == "SP:":
        # Phase 659: SP:'s own real grammar is always tactic-list-shaped
        # (no leading "tl" slot the way a Search/Challenge/Pursue phase's
        # own `extra` has -- see `_consume_search_extra()`'s own Phase
        # 659 addendum), so it's parsed unconditionally via the shared
        # walk rather than peeked at like a phase's own action code.
        sp_values, i = _consume_tactic_list(tokens, token_line, lines, i + 1)
        segment.sp = tuple(sp_values)

    for label_num in range(plan_start, plan_end + 1):
        label = f"P{label_num}"
        if i >= len(tokens) or tokens[i] != label:
            found = repr(tokens[i]) if i < len(tokens) else "<end of tokens>"
            raise K1ParseError(f"{owner_desc}: expected phase {label!r} at this position, got {found}")

        # Phase 618: peek (non-destructively) at what would be `action_val`
        # to see whether this phase needs the SAY-aware walk below
        # instead of the generic `consume_ints()` sweep, which would
        # crash the instant it hit a real SAY tactic's own free text.
        # Every other phase (the overwhelming majority, and the fallback
        # for anything this peek can't cleanly resolve) takes the *exact*
        # pre-existing code path, unchanged -- this is what keeps every
        # real AK3__T*.K1 sample byte-identical to before this phase.
        # Phase 659: widened from Search alone -- `turn/challenge_pursue_
        # decode.py`'s own module docstring already confirms Challenge/
        # Pursue share exactly the same `extra` shape (`tl` + tactic
        # list), so they need the identical walk, not a separate one.
        phase_start = i + 1
        while phase_start < len(tokens) and tokens[phase_start] == ":":
            phase_start += 1  # consume_ints()'s own "P0 : 12 6 0" colon-skip, replicated for the peek below
        is_tactic_list_action = False
        if phase_start < len(tokens):
            try:
                is_tactic_list_action = action_from_int(int(tokens[phase_start])) in (
                    ActionCode.SEARCH,
                    ActionCode.CHALLENGE,
                    ActionCode.PURSUE,
                )
            except ValueError:
                is_tactic_list_action = False

        if is_tactic_list_action:
            action_val = int(tokens[phase_start])
            obj_val = int(tokens[phase_start + 1]) if phase_start + 1 < len(tokens) else 0
            extra_val, i = _consume_search_extra(tokens, token_line, lines, phase_start + 2)
        else:
            values, i = consume_ints(tokens, i + 1)
            action_val = values[0] if values else 0
            obj_val = values[1] if len(values) > 1 else 0
            extra_val = values[2:] if len(values) > 2 else []
        phase = PlanPhase(label=label, action=action_from_int(action_val), obj=obj_val, extra=extra_val)

        phase.nested_plan, i = _maybe_parse_nested_plan(
            tokens, i, phase, label_num, owner_desc=owner_desc, token_line=token_line, lines=lines, depth=depth
        )
        segment.phases[label] = phase

    return segment, i


def _consume_search_extra(
    tokens: list[str], token_line: list[int], lines: list[str], i: int
) -> tuple[list[int | str], int]:
    """Like ``consume_ints()``, but Search/Challenge/Pursue-tactic-aware
    (Phase 618, widened Phase 659): walks a phase's own ``Tac_Bytes``
    tactic list -- see ``_consume_tactic_list()`` below for the walk
    itself.

    ``extra[0]`` (``"tl"``, ``SearchRequest.unconfirmed_extra0``/
    ``ChallengeRequest``/``PursueRequest``'s own field of the same name
    -- always ``0`` in every real sample, per ``turn/search_decode.py``'s
    own docstring) is *not* itself a tactic ordinal -- read as one plain
    int first, unconditionally, exactly like ``consume_ints()`` would,
    before the maneuver-classified walk begins. Skipping this
    distinction would misread ``tl``'s own ``0`` as a ``CAST`` ordinal
    and eat the *real* first tactic's own ordinal as if it were
    ``CAST``'s sub-object. ``SP:`` (Phase 659) has no such leading slot
    -- see ``_consume_tactic_list()``, called directly for that case.
    """

    values: list[int | str] = []
    if i < len(tokens) and not is_keyword(tokens[i]):
        try:
            values.append(int(tokens[i]))
        except ValueError as exc:
            raise K1ParseError(f"expected an integer or keyword in a Search phase, got {tokens[i]!r}") from exc
        i += 1

    tactic_values, i = _consume_tactic_list(tokens, token_line, lines, i)
    values.extend(tactic_values)
    return values, i


def _consume_tactic_list(
    tokens: list[str], token_line: list[int], lines: list[str], i: int
) -> tuple[list[int | str], int]:
    """The shared tactic-list walk itself (Phase 618, extracted as its own
    function Phase 659 so ``SP:``'s own plan-level list -- which has no
    leading ``tl`` slot -- can reuse it directly): one ``Maneuver``
    ordinal at a time, classifying each the same way ``turn/search_
    decode.py decode_search_phase()``'s own walk does -- ``SAY`` recovers
    its own free text via ``_recover_say_text()`` below instead of
    reading a plain int; anything in ``TACTICS_WITH_SUB_OBJECT``
    (``CAST``/``USE_MI``/``GIVE``) reads one more plain int as before;
    everything else (a bare ``MELEE``/``FLEE``/``SCOUT``/``STEAL``/
    ``SHOOT``, the list's own ``-1`` terminator, or any other raw int) is
    kept as-is with no special handling -- deliberately kept in sync with
    that module's own walk (see this module's own Phase 618/659
    addenda).
    """

    values: list[int | str] = []
    while i < len(tokens):
        token = tokens[i]
        if is_keyword(token):
            break
        try:
            value = int(token)
        except ValueError as exc:
            raise K1ParseError(f"expected an integer or keyword in a tactic list, got {token!r}") from exc
        values.append(value)
        i += 1

        maneuver = maneuver_from_int(value)
        if maneuver is Maneuver.SAY:
            text, i = _recover_say_text(token_line[i - 1], lines, token_line, i)
            values.append(text)
        elif maneuver in TACTICS_WITH_SUB_OBJECT and i < len(tokens):
            values.append(int(tokens[i]))
            i += 1
    return values, i


def _recover_say_text(
    ordinal_line_index: int, lines: list[str], token_line: list[int], i: int
) -> tuple[str, int]:
    """Recovers a ``SAY`` tactic's own free-text argument directly from
    the move file's raw lines (Phase 618) -- confirmed real shape (see
    ``turn/search_decode.py``'s own module docstring): the text sits on
    the line(s) immediately after the ``SAY`` ordinal's own line,
    terminated by a blank line (a line that's empty or all-whitespace, a
    small robustness generalization of the Pascal reader's own literal
    ``(tmp = '') or (tmp = ' ')`` check).

    Returns the recovered text (multiple lines joined with a single
    space, mirroring ``Concat(sayeth, tmp, ' ')`` minus the Pascal
    original's own trailing space -- cosmetic, not a meaning change) and
    the flat token index to resume parsing at: every token whose own
    ``token_line`` falls within the consumed text lines is skipped, since
    those words were already split into ``tokens`` by the initial
    tokenization pass just like any other line's words.
    """

    cursor = ordinal_line_index + 1
    text_lines: list[str] = []
    while True:
        if cursor >= len(lines):
            raise K1ParseError(
                f"a SAY tactic's own free text (starting after line {ordinal_line_index}) "
                "was never terminated by a blank line"
            )
        stripped = lines[cursor].strip()
        if stripped == "":
            break
        text_lines.append(stripped)
        cursor += 1

    while i < len(token_line) and token_line[i] < cursor:
        i += 1

    return " ".join(text_lines), i


def _maybe_parse_nested_plan(
    tokens: list[str],
    i: int,
    phase: PlanPhase,
    label_num: int,
    *,
    owner_desc: str,
    token_line: list[int],
    lines: list[str],
    depth: int = 0,
) -> tuple[ActionPlan | None, int]:
    """If ``phase`` triggers a nested plan, parse and return it; else ``(None, i)`` unchanged.

    Sourced from ``HostAK/TP/DEF2.PAS`` (~line 505: "IF m < 4 THEN
    R_HPLan(...)"): only a phase in position ``P0``-``P3`` can trigger
    this -- ``P4`` never does, which is exactly what disambiguates a
    nested plan from a genuine new sibling ``AP:`` segment for the same
    leader (only possible right after a ``P4``).
    """

    if label_num >= 4 or i >= len(tokens) or tokens[i] != "AP:":
        return None, i

    # Hire's own `obj` *is* the target character's id (rulebook [3.5]).
    # A Cast of Charm or Resurrection is the other nesting trigger
    # (`DEF2.PAS Read_More`: "Charm, Resurrection: Read_HPlan") -- there,
    # `obj` is the *spell* id, not a character id, but the spell's own
    # target (`extra[0]`, per `turn/cast_decode.py`) is the character
    # being charmed/resurrected, i.e. the newly-joined leader's id. Any
    # other Cast (or any other action) triggering this structurally
    # (next token is `AP:`) has no recoverable owning-character id.
    if phase.action is ActionCode.HIRE:
        nested_leader_id = phase.obj
    elif phase.action is ActionCode.CAST and phase.obj in (Spell.CHARM, Spell.RESURRECTION) and phase.extra:
        nested_leader_id = phase.extra[0]
    else:
        nested_leader_id = None
    return _parse_action_plan(
        tokens,
        i,
        nested_leader_id,
        owner_desc=f"{owner_desc} > nested plan",
        token_line=token_line,
        lines=lines,
        depth=depth + 1,
    )
