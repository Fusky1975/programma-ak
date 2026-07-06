"""Low-level tokenizing helpers for the .K1 move-submission format.

Within a leader's move block, keywords (``AP:``, ``SP:``, ``P0``..``P4``)
mark the start of a value group; everything up to the next keyword is data
for that group. Phase keywords are sometimes followed by a lone ``:`` token
(e.g. ``P0 : 12 6 0``), while ``AP:``/``SP:`` have the colon glued on.
"""

from __future__ import annotations

import re

from ak_engine.parser.errors import K1ParseError

_KEYWORD_RE = re.compile(r"^(AP:|SP:|P[0-4])$")
_LEADER_HEADER_RE = re.compile(r"^(\d+)\s+-(.+)$")


def is_keyword(token: str) -> bool:
    return bool(_KEYWORD_RE.match(token))


def flatten_tokens(lines: list[str]) -> list[str]:
    """Whitespace-split a block of lines into one flat token stream, skipping blanks."""

    tokens: list[str] = []
    for line in lines:
        tokens.extend(line.split())
    return tokens


def match_leader_header(line: str) -> tuple[int, str] | None:
    """Match a leader block header line like ``1 -Uga-Buga Makumb``."""

    match = _LEADER_HEADER_RE.match(line.strip())
    if match is None:
        return None
    return int(match.group(1)), match.group(2)


def consume_ints(tokens: list[str], index: int) -> tuple[list[int], int]:
    """Collect consecutive integer tokens starting at ``index``.

    Stops at the next keyword token or the end of the stream. A lone ``:``
    token (used after bare ``P0``..``P4`` keywords) is skipped rather than
    treated as data.
    """

    values: list[int] = []
    while index < len(tokens):
        token = tokens[index]
        if token == ":":
            index += 1
            continue
        if is_keyword(token):
            break
        try:
            values.append(int(token))
        except ValueError as exc:
            raise K1ParseError(f"expected an integer or keyword, got {token!r}") from exc
        index += 1
    return values, index
