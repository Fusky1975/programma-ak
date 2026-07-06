"""Tests for the .K1 move-submission parser, against real game data files.

Fixtures come straight from the repo's parent folder (the original game
data), not copies, so there is a single source of truth. Only the
``AK3__T*.K1`` series is used here: they are genuine player move
submissions. The ``SE3__T*.K1`` series (same extension, different content)
are generated turn *reports* -- narrative prose, not move data -- and
``GW3__T*`` files use a different dense numeric format entirely. Both are
intentionally excluded from these fixtures; don't add them here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ak_engine.models.enums import ActionCode
from ak_engine.parser.errors import K1ParseError
from ak_engine.parser.k1_moves import parse_k1_moves_file

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
ALL_MOVE_FILES = [GAME_DATA_DIR / f"AK3__T{i}.K1" for i in range(1, 11)]


@pytest.mark.parametrize("path", ALL_MOVE_FILES, ids=lambda p: p.name)
def test_parses_without_error(path: Path) -> None:
    kingdom = parse_k1_moves_file(path)
    assert kingdom.source_filename == path.name
    assert kingdom.king_name
    assert kingdom.leaders


@pytest.mark.parametrize("path", ALL_MOVE_FILES, ids=lambda p: p.name)
def test_skill_table_always_has_31_values(path: Path) -> None:
    kingdom = parse_k1_moves_file(path)
    assert len(kingdom.skills.raw_values) == 31


def test_ak3_t1_exact_values() -> None:
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")

    assert kingdom.king_name == "Uga-Buga Makumb"
    assert kingdom.king_title == "Shaman"
    assert [leader.leader_id for leader in kingdom.leaders] == [1, 18, 72]

    king = kingdom.leaders[0]
    assert king.name == "Uga-Buga Makumb"
    segment = king.plan.segments[0]
    assert segment.plan_start == 0
    assert segment.plan_end == 4
    assert segment.sp == (10, -1)

    guerin = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    p3 = guerin.plan.segments[0].phases["P3"]
    assert p3.action == ActionCode.LEAVE
    assert p3.obj == 0
    assert p3.extra == [1, 108, 109, 110, -1]

    assert kingdom.trailer_comments == ""


def test_ak3_t10_last_leader_and_multi_segment_plan() -> None:
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T10.K1")

    assert kingdom.leaders[-1].leader_id == 97
    assert kingdom.leaders[-1].name == "Odysseus"

    king = kingdom.leaders[0]
    assert len(king.plan.segments) > 1, "leader 1 in T10 submits moves across multiple AP:/SP: segments"


def test_no_tokens_lost_between_leader_blocks_and_sentinel() -> None:
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T3.K1")

    for leader in kingdom.leaders:
        for segment in leader.plan.segments:
            assert segment.phases, f"leader {leader.leader_id} has a segment with no phases at all"


def test_malformed_skill_line_raises(tmp_path: Path) -> None:
    original = (GAME_DATA_DIR / "AK3__T1.K1").read_text(encoding="utf-8")
    lines = original.splitlines()
    skill_line_index = next(i for i, line in enumerate(lines) if line.strip().startswith("0 2 0 2"))
    lines[skill_line_index] = "0 2 0 2"  # too few values
    broken_file = tmp_path / "AK3__Broken.K1"
    broken_file.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(K1ParseError):
        parse_k1_moves_file(broken_file)
