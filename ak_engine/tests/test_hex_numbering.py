from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.enums import ActionCode
from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import parse_gw_leaders
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.hex_numbering import (
    EMPIRICAL_AK3_BOARD_WIDTH,
    decode_hex_number,
    encode_hex_number,
)
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, is_adjacent, neighbors

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
GW3_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "world" / "G3"


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


# -- Phase 916: a third/fourth real game's own LMOVE data, checked for the
# first time against this question -- see the module docstring for the
# full derivation and why this is weaker (n=1) evidence than the AK3/AK6
# sweeps above, not a replacement for them. Neither AK900T1.K0 nor its
# GW900T1 world-save is in this repo's fixtures (they were user-supplied
# for an unrelated question, Phase 907), so the real values are inlined
# here rather than read live, matching this project's convention for
# real-sample regression tests whose own source file isn't committed
# (e.g. test_king_talent.py's AK3__T1.K1 cross-check).


def test_ak900_real_leader_coordinate_and_lmove_target_fit_five_widths():
    # GW900T1's own parse_gw_leaders(): Legolas/Ashley/Negumba (Kingdom 0)
    # all start turn 1 at (6, 2). AK900T1.K0's own move file: all 3 issue
    # exactly one LMOVE, to target 61 -- the only usable (origin, target)
    # pair this game's single available turn yields.
    origin = HexCoord(6, 2)
    target_number = 61
    bounds = MapBounds(400, 400)

    matching_widths = [
        width for width in range(2, 201) if decode_hex_number(target_number, width) in neighbors(origin, bounds)
    ]

    assert matching_widths == [18, 27, 28, 54, 55]


def test_ak900s_own_real_board_width_is_among_the_matching_widths():
    # GW900T1's own header: map_right_x=17, map_bottom_y=8 -> an 18x9
    # real board. Width 18 is one of the 5 candidates above -- the first
    # of 3 real games checked (AK3, AK6, AK900) where the real board
    # width is even consistent with an actual LMOVE pair, though with
    # only one pair to go on this doesn't single 18 out as the best fit
    # the way AK3's 59 pairs or AK6's 15 did for their own empirical
    # widths.
    real_board_width = 18  # map_right_x(17) - map_left_x(0) + 1
    origin = HexCoord(6, 2)
    target_number = 61
    bounds = MapBounds(400, 400)

    decoded = decode_hex_number(target_number, real_board_width)
    assert decoded in neighbors(origin, bounds)


# -- Phase 917: ground-truth-anchored pairs from GW3__T1-T12's own real
# leader coordinates (parse_gw_leaders()), matched by name against each
# turn's own AK3__T*.K1 -- a genuinely independent dataset from Phase
# 315's own within-file consecutive-pair method (neither end of a Phase
# 315 pair is ever independently verified; here the "from" side is a
# real, undecoded world-save coordinate). See the module docstring for
# the full derivation, including why a straight (unswapped) comparison
# fails and the x/y transpose that fixes it.


def _ground_truth_anchored_pairs():
    pairs: list[tuple[HexCoord, int]] = []
    for turn in range(1, 11):
        kingdom = parse_k1_moves_file(GAME_DATA_DIR / f"AK3__T{turn}.K1")
        gw_leaders = {r.name: r.coord for r in parse_gw_leaders(GW3_FIXTURE_DIR / f"GW3__T{turn}")}
        for leader in kingdom.leaders:
            real_coord = gw_leaders.get(leader.name)
            if real_coord is None or not leader.plan.segments:
                continue
            segment = leader.plan.segments[0]
            target = None
            blocked = False
            for label in _PHASE_ORDER:
                phase = segment.phases.get(label)
                if phase is None:
                    continue
                if phase.action == ActionCode.LMOVE:
                    target = phase.obj
                    break
                if phase.action in (ActionCode.PURSUE, ActionCode.TRAIL, ActionCode.SUCC_TRAIL):
                    blocked = True
                    break
            if target is not None and not blocked:
                # The transpose: GWLeaderRecord.coord's own (x, y) convention
                # is swapped relative to this module's row-major decode --
                # see the module docstring's own Phase 917 addendum.
                pairs.append((HexCoord(real_coord.y, real_coord.x), target))
    return pairs


def test_ground_truth_anchored_dataset_has_85_pairs():
    assert len(_ground_truth_anchored_pairs()) == 85


def test_width_10_matches_87_percent_of_ground_truth_anchored_pairs():
    pairs = _ground_truth_anchored_pairs()
    matches = sum(1 for coord, target in pairs if coord in neighbors(decode_hex_number(target, EMPIRICAL_AK3_BOARD_WIDTH), _IGNORE_EDGES_BOUNDS))
    assert matches / len(pairs) >= 0.87


def test_width_10_decisively_beats_every_other_width_on_ground_truth_pairs():
    pairs = _ground_truth_anchored_pairs()

    def score(width: int) -> int:
        return sum(1 for coord, target in pairs if coord in neighbors(decode_hex_number(target, width), _IGNORE_EDGES_BOUNDS))

    width_10_score = score(EMPIRICAL_AK3_BOARD_WIDTH)
    other_scores = [score(w) for w in range(2, 201) if w != EMPIRICAL_AK3_BOARD_WIDTH]
    assert width_10_score > max(other_scores)


def test_unswapped_leader_coordinates_fail_at_every_width():
    # The negative half of the same finding: without the transpose, no
    # width in 2-200 recovers a meaningful match rate -- a flat failure,
    # not noise, which is what pointed at a wrong-basis comparison
    # rather than a weak fit.
    pairs_unswapped: list[tuple[HexCoord, int]] = []
    for turn in range(1, 11):
        kingdom = parse_k1_moves_file(GAME_DATA_DIR / f"AK3__T{turn}.K1")
        gw_leaders = {r.name: r.coord for r in parse_gw_leaders(GW3_FIXTURE_DIR / f"GW3__T{turn}")}
        for leader in kingdom.leaders:
            real_coord = gw_leaders.get(leader.name)
            if real_coord is None or not leader.plan.segments:
                continue
            segment = leader.plan.segments[0]
            for label in _PHASE_ORDER:
                phase = segment.phases.get(label)
                if phase is None:
                    continue
                if phase.action == ActionCode.LMOVE:
                    pairs_unswapped.append((real_coord, phase.obj))
                break

    def score(width: int) -> int:
        return sum(1 for coord, target in pairs_unswapped if coord in neighbors(decode_hex_number(target, width), _IGNORE_EDGES_BOUNDS))

    best_unswapped_score = max(score(w) for w in range(2, 201))
    assert best_unswapped_score / len(pairs_unswapped) < 0.2


# -- Phase 918: Phase 917's own row-parity comparison above had a real bug
# (its "reversed" convention was, worked through by hand, identical to the
# real corrected one, not its negation) -- these replace it with a
# correctly-negated comparison. See the module docstring's own Phase 918
# addendum for the full derivation.


def _reversed_neighbors(coord, bounds):
    from ak_engine.turn.movement import _EVEN_ROW_OFFSETS, _ODD_ROW_OFFSETS

    # The true negation of movement.py neighbors()'s own
    # `_EVEN_ROW_OFFSETS if coord.y % 2 else _ODD_ROW_OFFSETS`.
    offsets = _ODD_ROW_OFFSETS if coord.y % 2 else _EVEN_ROW_OFFSETS
    return [
        HexCoord(coord.x + dx, coord.y + dy)
        for dx, dy in offsets
        if 0 <= coord.x + dx < bounds.width and 0 <= coord.y + dy < bounds.height
    ]


def test_row_parity_genuinely_discriminates_the_ground_truth_dataset():
    # Corrected replacement for Phase 917's own (buggy) "undiscriminated"
    # test: with a truly-reversed convention, 27 of the 85 pairs really
    # do flip, and the corrected convention wins the split (16 vs 11).
    # Uses the same generous, non-clipping bounds as the width-sweep test
    # below -- this module's own board reaches past its declared 15-row
    # height, so a tight bounds check would distort the comparison.
    pairs = _ground_truth_anchored_pairs()
    corrected_hits = sum(1 for coord, target in pairs if coord in neighbors(decode_hex_number(target, EMPIRICAL_AK3_BOARD_WIDTH), _IGNORE_EDGES_BOUNDS))
    reversed_hits = sum(
        1 for coord, target in pairs if coord in _reversed_neighbors(decode_hex_number(target, EMPIRICAL_AK3_BOARD_WIDTH), _IGNORE_EDGES_BOUNDS)
    )
    assert corrected_hits == 74
    assert reversed_hits == 69


def test_original_59_pair_dataset_actually_favors_the_corrected_convention():
    # The pre-existing "52 vs 50" figure (module docstring, Phase 315)
    # had both numbers right but credited them to the wrong convention:
    # 52 is the corrected convention's own (generous-bounds) score, not
    # the reversed one's. Same generous bounds as the test above, for
    # the same reason.
    pairs = _consecutive_lmove_pairs_in_final_segments()
    corrected_hits = sum(
        1
        for a, b in pairs
        if decode_hex_number(b, EMPIRICAL_AK3_BOARD_WIDTH) in neighbors(decode_hex_number(a, EMPIRICAL_AK3_BOARD_WIDTH), _IGNORE_EDGES_BOUNDS)
    )
    reversed_hits = sum(
        1
        for a, b in pairs
        if decode_hex_number(b, EMPIRICAL_AK3_BOARD_WIDTH) in _reversed_neighbors(decode_hex_number(a, EMPIRICAL_AK3_BOARD_WIDTH), _IGNORE_EDGES_BOUNDS)
    )
    assert corrected_hits == 52
    assert reversed_hits == 50


def test_17_of_18_known_non_adjacent_pairs_are_the_parity_sensitive_diagonal():
    # Answers "what does the ~15% of non-adjacent pairs represent"
    # precisely: combining both real datasets (generous bounds), all but
    # one of the known corrected-convention failures are exactly a
    # (+-1, +-1) diagonal step -- the same delta that differs between the
    # two parity tables -- not chasing, not a different action, not a
    # decode error. The sole exception is the already-known 170
    # sentinel-like jump.
    sensitive_deltas = {(1, 1), (-1, -1), (1, -1), (-1, 1)}
    non_adjacent_deltas = []

    for a, b in _consecutive_lmove_pairs_in_final_segments():
        ca, cb = decode_hex_number(a, EMPIRICAL_AK3_BOARD_WIDTH), decode_hex_number(b, EMPIRICAL_AK3_BOARD_WIDTH)
        if cb not in neighbors(ca, _IGNORE_EDGES_BOUNDS):
            non_adjacent_deltas.append((cb.x - ca.x, cb.y - ca.y))

    for coord, target in _ground_truth_anchored_pairs():
        decoded = decode_hex_number(target, EMPIRICAL_AK3_BOARD_WIDTH)
        if coord not in neighbors(decoded, _IGNORE_EDGES_BOUNDS):
            non_adjacent_deltas.append((coord.x - decoded.x, coord.y - decoded.y))

    assert len(non_adjacent_deltas) == 18
    diagonal_count = sum(1 for delta in non_adjacent_deltas if delta in sensitive_deltas)
    assert diagonal_count == 17
