from __future__ import annotations

import pytest

from ak_engine.models.map import HexCoord
from ak_engine.turn.hex_numbering import decode_hex_number, encode_hex_number


def test_decode_matches_row_major_formula():
    assert decode_hex_number(104, board_width=10) == HexCoord(4, 10)
    assert decode_hex_number(0, board_width=10) == HexCoord(0, 0)
    assert decode_hex_number(9, board_width=10) == HexCoord(9, 0)
    assert decode_hex_number(10, board_width=10) == HexCoord(0, 1)


def test_encode_is_the_inverse_of_decode():
    for number in [0, 9, 10, 55, 104, 171]:
        coord = decode_hex_number(number, board_width=10)
        assert encode_hex_number(coord, board_width=10) == number


def test_rejects_bad_board_width():
    with pytest.raises(ValueError):
        decode_hex_number(5, board_width=0)
    with pytest.raises(ValueError):
        encode_hex_number(HexCoord(0, 0), board_width=-1)


def test_rejects_negative_number():
    with pytest.raises(ValueError):
        decode_hex_number(-1, board_width=10)
