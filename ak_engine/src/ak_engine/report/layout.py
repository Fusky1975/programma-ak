"""Turn-report text layout, reproducing the original Pascal engine's own
flowing of prose (``HostAK/TP/YAK.PAS`` ``Spread``/``Write_It``).

What the original does, verified paragraph by paragraph against the real
``SE3__T*.K1`` reports (every engine-written paragraph of those 12 files
re-wraps to exactly the same lines):

- a report line is at most ``REPORT_WIDTH`` (77) columns; text is written word
  by word and a word that would cross the margin starts a new line, so every
  wrapped line keeps its trailing space;
- each *paragraph* (the start of a phase's narrative, a letter body, a quote)
  begins on its own line indented by two spaces; continuation lines are not
  indented;
- a sentence ending in ``.``/``?``/``!`` (optionally followed by a quote or a
  parenthesis) is followed by two spaces;
- a name -- a leader, a province, an army type, a spell -- is written as one
  indivisible unit, so it is never split across two lines.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

REPORT_WIDTH = 77
NBSP = " "
PARAGRAPH_INDENT = "  "

_SENTENCE_END = re.compile(r"([.!?][\"')]?)(?=[A-Z])")
_SPACE_AFTER_SENTENCE = re.compile(r"([.!?][\"')]?) (?=[A-Z])")
_SPACE_RUN = re.compile(r" {2,}")
_ENDS_SENTENCE = re.compile(r"[.!?][\"')]?$")


def normalize_sentences(text: str) -> str:
    """Two spaces after every sentence end: ``"...here.The next"`` and
    ``"...here. The next"`` both become ``"...here.  The next"``."""

    text = _SPACE_RUN.sub(" ", text)
    text = _SENTENCE_END.sub(r"\1  ", text)
    text = _SPACE_AFTER_SENTENCE.sub(r"\1  ", text)
    return text


def protect_units(text: str, units: Iterable[str]) -> str:
    """Joins the spaces inside every known multi-word name (and before a
    ``(#12)`` identifier) with non-breaking spaces so ``flow_paragraph()``
    keeps each name on one line. ``unprotect()`` undoes it."""

    for unit in sorted({u for u in units if " " in u}, key=len, reverse=True):
        if unit in text:
            text = text.replace(unit, unit.replace(" ", NBSP))
    return re.sub(r" (?=\(#\d+\))", NBSP, text)


def unprotect(text: str) -> str:
    return text.replace(NBSP, " ")


def flow_paragraph(text: str, *, width: int = REPORT_WIDTH, indent: str = PARAGRAPH_INDENT) -> list[str]:
    """Flows ``text`` into report lines: ``indent`` on the first line only,
    greedy word wrap at ``width`` columns, trailing space kept at a wrap."""

    tokens = re.findall(r"[^ \n]+|[ \n]+", text.strip(" "))
    lines: list[str] = []
    current = ""
    column = 1
    for char in indent:
        current += char
        column += 1
    for token in tokens:
        if token[0] in " \n":
            for _ in token:
                if column != 1 and column <= width:
                    current += " "
                    column += 1
            continue
        if column + len(token) > width and column != 1:
            lines.append(current)
            current = ""
            column = 1
        current += token
        column += len(token)
    if current:
        lines.append(current)
    return [unprotect(line) for line in lines]


def flow_sentences(sentences: Iterable[str], *, units: Iterable[str] = (), width: int = REPORT_WIDTH) -> list[str]:
    """One paragraph from several sentence-sized strings: joined with the
    sentence spacing, names kept whole, flowed with the paragraph indent."""

    parts: list[str] = []
    for sentence in (s.strip() for s in sentences if s and s.strip()):
        # The original capitalizes the first letter of a unit that starts a
        # sentence or a paragraph (``YAK.PAS Spread``'s ``makeup``).
        if not parts or _ENDS_SENTENCE.search(parts[-1]):
            sentence = sentence[0].upper() + sentence[1:]
        parts.append(sentence)
    text = protect_units(normalize_sentences(" ".join(parts)), units)
    return flow_paragraph(text, width=width)


_PROSE_LINE_MIN_LENGTH = 40
_PROSE_LINE_MIN_WORDS = 7
_PROSE_GAP = re.compile(r"(?<![.!?\"')]) {2,}")


def looks_like_prose(line: str) -> bool:
    """A report line that is running text (an introduction, a closing
    remark) rather than a table row, a heading or a figure: long enough, many
    words, no column-aligning runs of spaces."""

    if not line or line.startswith(" ") or len(line) < _PROSE_LINE_MIN_LENGTH:
        return False
    if len(line.split()) < _PROSE_LINE_MIN_WORDS:
        return False
    return _PROSE_GAP.search(line.rstrip()) is None


def flow_prose_in_lines(lines: list[str], *, units: Iterable[str] = (), width: int = REPORT_WIDTH) -> list[str]:
    """Reflows every prose line of an already-composed section list the way
    the original writes its fixed introductions: two-space indent, wrapped at
    ``width``; every other line passes through unchanged."""

    out: list[str] = []
    units = list(units)
    for line in lines:
        if looks_like_prose(line):
            out.extend(flow_sentences([line], units=units, width=width))
        else:
            out.append(line)
    return out
