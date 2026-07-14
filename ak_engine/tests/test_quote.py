from __future__ import annotations

import pytest

from ak_engine.models.quote import QUOTES, quote_of_the_week


def test_quotes_has_94_declared_blocks():
    assert len(QUOTES) == 94


def test_quotes_every_block_is_a_two_line_tuple():
    assert all(isinstance(block, tuple) and len(block) == 2 for block in QUOTES)


def test_quote_of_the_week_first_block_verbatim():
    assert quote_of_the_week(0) == (
        '"The King of England has men, horses, silk, jewels, fruit, game and everything '
        'else.  And we in France have nothing but bread and wine and gaiety!"',
        "-Louis VII, King of France, 1179 A.D.",
    )


def test_quote_of_the_week_last_block_verbatim():
    assert quote_of_the_week(93) == (
        "William I, first Norman King of England, 1066:",
        '"It is in the defence of right that I have crossed the sea into this country. '
        "I do not think it right that my men or Harold's men should perish in a quarrel "
        'that is none of their making. I am therefore ready to risk my life in a duel to '
        'the death."',
    )


def test_quote_of_the_week_some_blocks_state_speaker_before_the_quote():
    # Confirms the "verbatim source order, not normalized" claim in the
    # module docstring: block index 1 (the file's own 2nd block) states
    # the speaker before the quote rather than as a trailing attribution.
    first_line, second_line = quote_of_the_week(1)
    assert first_line == "St. Louis IX, King of France, speaking to his son in 1244 A.D.:"
    assert second_line.startswith('"')


def test_quote_of_the_week_out_of_range_raises_index_error():
    with pytest.raises(IndexError):
        quote_of_the_week(94)
