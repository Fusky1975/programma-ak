from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.enums import ActionCode
from ak_engine.models.map import HexCoord
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.hex_numbering import (
    EMPIRICAL_AK3_BOARD_WIDTH,
    decode_hex_number,
    encode_hex_number,
)
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, is_adjacent

GAME_DATA_DIR = Path(__file__).resolve().parents[2]


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


# -- Phase 315: real-file re-validation of the width=10 hypothesis -----------
#
# Re-derives the module docstring's "59 pairs" figure directly from the real
# `AK3__T*.K1` fixtures via the project's own parser, rather than trusting a
# lost ad-hoc script. See `turn/hex_numbering.py`'s module docstring for the
# full methodology and the alternative hypotheses ruled out.

_PHASE_ORDER = ("P0", "P1", "P2", "P3", "P4")
_IGNORE_EDGES_BOUNDS = MapBounds(1000, 1000)


def _consecutive_lmove_pairs_in_final_segments():
    pairs: list[tuple[int, int]] = []
    for i in range(1, 11):
        kingdom = parse_k1_moves_file(GAME_DATA_DIR / f"AK3__T{i}.K1")
        for leader in kingdom.leaders:
            if not leader.plan.segments:
                continue
            segment = leader.plan.segments[-1]
            run: list[int] = []
            for label in _PHASE_ORDER:
                phase = segment.phases.get(label)
                if phase is not None and phase.action == ActionCode.LMOVE:
                    run.append(phase.obj)
                else:
                    pairs.extend(zip(run, run[1:]))
                    run = []
            pairs.extend(zip(run, run[1:]))
    return pairs


def test_real_move_file_lmove_pairs_yield_the_59_pair_dataset():
    # Confirms the module docstring's re-derived pair count is reproducible
    # straight from the fixtures, not a one-off manual tally.
    assert len(_consecutive_lmove_pairs_in_final_segments()) == 59


def test_width_10_matches_over_84_percent_of_real_lmove_pairs():
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    pairs = _consecutive_lmove_pairs_in_final_segments()
    matches = sum(
        1
        for a, b in pairs
        if is_adjacent(
            decode_hex_number(a, EMPIRICAL_AK3_BOARD_WIDTH),
            decode_hex_number(b, EMPIRICAL_AK3_BOARD_WIDTH),
            bounds,
        )
    )
    assert matches / len(pairs) >= 0.84


def test_width_10_decisively_beats_every_other_width_2_to_200():
    pairs = _consecutive_lmove_pairs_in_final_segments()

    def score(width: int) -> int:
        return sum(
            1
            for a, b in pairs
            if is_adjacent(
                decode_hex_number(a, width), decode_hex_number(b, width), _IGNORE_EDGES_BOUNDS
            )
        )

    width_10_score = score(EMPIRICAL_AK3_BOARD_WIDTH)
    other_scores = [score(w) for w in range(2, 201) if w != EMPIRICAL_AK3_BOARD_WIDTH]
    assert width_10_score > max(other_scores)


def test_se3_report_style_row_times_100_plus_col_is_ruled_out_for_ak3_lmove():
    # Phase 315: the row*100+col scheme confirmed for SE3 report-file
    # province numbers (turn/movement.py's own docstring) does NOT describe
    # AK3 LMOVE targets -- a different, incompatible numbering scheme.
    pairs = _consecutive_lmove_pairs_in_final_segments()
    matches = sum(
        1
        for a, b in pairs
        if is_adjacent(
            HexCoord(a // 100, a % 100), HexCoord(b // 100, b % 100), _IGNORE_EDGES_BOUNDS
        )
    )
    assert matches / len(pairs) < 0.30
