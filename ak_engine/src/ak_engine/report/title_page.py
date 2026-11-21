"""Title page and "Quote of the Week" of a turn report, laid out like the
original program's own (``REPORTS.PAS Title_Page``/``Basic_Report``,
verified against the real ``SE3__T*.K1`` files): title lines centered on a
71-column page (left-biased), the quote's header and its two source lines
written as ordinary indented, wrapped paragraphs."""

from __future__ import annotations

from ak_engine.models.quote import quote_of_the_week
from ak_engine.report.layout import flow_paragraph

TITLE_PAGE_WIDTH = 71
QUOTE_COUNT = 94


def centered(text: str, width: int = TITLE_PAGE_WIDTH) -> str:
    pad = max(width - len(text), 0)
    return " " * ((pad + 1) // 2) + text


def quote_index_for_turn(game_number: int, turn_number: int) -> int:
    """One quote per game turn, shared by every Kingdom (the original picks
    it from the calendar, which a saved game cannot reproduce)."""

    return (turn_number * 37 + game_number * 11) % QUOTE_COUNT


def quote_block(index: int) -> list[str]:
    """"Quote of the Week:", a blank line, then the quote's source lines as
    flowed paragraphs."""

    first, second = quote_of_the_week(index)
    lines = ["  Quote of the Week:", ""]
    for text in (first, second):
        if text and text.strip():
            lines.extend(flow_paragraph(text))
    return lines


def processed_turn_title_lines(game_number: int, turn_number: int, king_name: str | None) -> list[str]:
    """The title page + quote that opens every processed turn's report."""

    lines = ["", "", centered(f"ADVENTURER-KINGS:  GAME {game_number}, TURN {turn_number}"), "", centered("FOR")]
    if king_name:
        lines.extend(["", centered(king_name.upper())])
    lines.extend([""] * 6)
    lines.extend(quote_block(quote_index_for_turn(game_number, turn_number)))
    lines.extend(["", ""])
    return lines
