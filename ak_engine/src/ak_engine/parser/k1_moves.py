"""Parser for the player move-submission .K1 format (e.g. AK3__T1.K1).

Not to be confused with the turn-report .K1 files produced by the original
engine (e.g. SE3__T0.K1), which are unrelated narrative text and are not
handled here.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

from ak_engine.models.enums import ActionCode, Spell, action_from_int
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader, SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.tokens import consume_ints, flatten_tokens, match_leader_header

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
    line = _line_at(lines, index, path)
    tokens = line.split()
    if not tokens or tokens[0] != "M":
        raise K1ParseError("expected kingdom header line starting with 'M'", line_number=index, line=line)
    try:
        raw_fields = [int(tok) for tok in tokens[1:]]
    except ValueError as exc:
        raise K1ParseError("kingdom header line contains a non-integer field", line_number=index, line=line) from exc
    return KingdomMoveHeader(raw_fields=raw_fields)


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
        elif stripped:
            if current_id is None:
                raise K1ParseError(
                    "unexpected content before first leader block",
                    line_number=i,
                    line=line,
                )
            body_lines.append(line)
        i += 1

    if sentinel_idx is None:
        raise K1ParseError(f"{path.name}: missing '255' sentinel terminating leader blocks")

    if current_id is not None:
        leaders.append(_build_leader(current_id, current_name, body_lines))

    trailer_comments = "\n".join(lines[sentinel_idx + 1 :]).strip()
    return leaders, trailer_comments


def _build_leader(leader_id: int, name: str | None, body_lines: list[str]) -> Leader:
    tokens = flatten_tokens(body_lines)
    plan, i = _parse_action_plan(tokens, 0, leader_id, owner_desc=f"leader {leader_id}")
    if i != len(tokens):
        raise K1ParseError(f"leader {leader_id}: unexpected trailing tokens after plan: {tokens[i:]!r}")

    return Leader(leader_id=leader_id, name=name or "", plan=plan)


def _parse_action_plan(
    tokens: list[str], i: int, leader_id: int | None, *, owner_desc: str
) -> tuple[ActionPlan, int]:
    """Parse as many consecutive ``AP:`` segments as appear at ``i``.

    Used both for a leader's own top-level plan and, recursively, for a
    nested Hire/Charm/Resurrection character's embedded plan (see
    ``models/plan.py``'s module docstring) -- the two are structurally
    identical, just entered from a different call site.
    """

    segments: list[PlanSegment] = []
    while i < len(tokens) and tokens[i] == "AP:":
        segment, i = _parse_segment(tokens, i, owner_desc=owner_desc)
        segments.append(segment)
    return ActionPlan(leader_id=leader_id, segments=segments), i


def _parse_segment(tokens: list[str], i: int, *, owner_desc: str) -> tuple[PlanSegment, int]:
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
        values, i = consume_ints(tokens, i + 1)
        segment.sp = tuple(values)

    for label_num in range(plan_start, plan_end + 1):
        label = f"P{label_num}"
        if i >= len(tokens) or tokens[i] != label:
            found = repr(tokens[i]) if i < len(tokens) else "<end of tokens>"
            raise K1ParseError(f"{owner_desc}: expected phase {label!r} at this position, got {found}")

        values, i = consume_ints(tokens, i + 1)
        action_val = values[0] if values else 0
        obj_val = values[1] if len(values) > 1 else 0
        extra_val = values[2:] if len(values) > 2 else []
        phase = PlanPhase(label=label, action=action_from_int(action_val), obj=obj_val, extra=extra_val)

        phase.nested_plan, i = _maybe_parse_nested_plan(tokens, i, phase, label_num, owner_desc=owner_desc)
        segment.phases[label] = phase

    return segment, i


def _maybe_parse_nested_plan(
    tokens: list[str], i: int, phase: PlanPhase, label_num: int, *, owner_desc: str
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
    return _parse_action_plan(tokens, i, nested_leader_id, owner_desc=f"{owner_desc} > nested plan")
