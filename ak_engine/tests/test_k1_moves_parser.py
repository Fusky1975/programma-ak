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


def test_ak3_t10_last_leader() -> None:
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T10.K1")

    assert kingdom.leaders[-1].leader_id == 97
    assert kingdom.leaders[-1].name == "Odysseus"


def test_ak3_t10_king_p1_cast_embeds_a_nested_plan() -> None:
    # Leader 1 (the King)'s raw text: "AP: 0 4 SP: 0 28 0 7 9 -1 P0 : 0 11 0
    # P1 : 9 12 78 AP: 2 4 SP: 10 -1  P2 : 9 4 0 P3 : 0 12 0 P4 : 9 6 13
    # P2 : 7 0 78 71 154 233 -1 P3 : 0 1 0 P4 : 0 171 0" -- this used to be
    # (mis-)parsed as "multiple AP:/SP: segments" for the King; it's
    # actually ONE segment whose P1 (a Cast of spell 12 = Charm, target
    # 78 -- see turn/cast_decode.py, Phase 23) embeds a nested plan for
    # the character it creates, spanning P2-P4, before the King's own
    # P2-P4 continue.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T10.K1")

    king = kingdom.leaders[0]
    assert len(king.plan.segments) == 1

    outer = king.plan.segments[0]
    p1 = outer.phases["P1"]
    assert p1.action == ActionCode.CAST
    assert p1.nested_plan is not None
    assert p1.nested_plan.leader_id == 78  # Charm's target (extra[0]) IS the charmed character's real id

    nested_segment = p1.nested_plan.segments[0]
    assert nested_segment.plan_start == 2
    assert nested_segment.plan_end == 4
    assert set(nested_segment.phases) == {"P2", "P3", "P4"}

    # The King's own P2-P4 continue correctly afterwards, not overwritten
    # by the nested character's same-labeled phases (the confirmed bug).
    assert outer.phases["P2"].action == ActionCode.LEAVE
    assert outer.phases["P2"].extra == [78, 71, 154, 233, -1]
    assert outer.phases["P4"].obj == 171


def test_ak3_t2_leader18_hire_embeds_hero32s_own_plan() -> None:
    # Raw text: "AP: 0 4 SP: -1 P0 : 0 104 0 P1 : 5 32 3 AP: 2 4 SP: -1
    # P2 : 0 94 0 P3 : 0 85 0 P4 : 0 96 0   P2 : 0 105 0 P3 : 9 2 95
    # P4 : 0 106 0" -- Guerin's Hire at P1 (hero 32, offer 3) used to
    # silently discard hero 32's own P2-P4 orders in favor of Guerin's
    # own later same-labeled phases; this is the confirmed bug's
    # flagship real-data example.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T2.K1")
    guerin = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    outer = guerin.plan.segments[0]

    p1 = outer.phases["P1"]
    assert p1.action == ActionCode.HIRE
    assert p1.obj == 32
    assert p1.nested_plan is not None
    assert p1.nested_plan.leader_id == 32  # Hire's obj IS the target hero's real id

    hero_segment = p1.nested_plan.segments[0]
    assert hero_segment.plan_start == 2
    assert hero_segment.plan_end == 4
    assert hero_segment.phases["P2"].obj == 94
    assert hero_segment.phases["P3"].obj == 85
    assert hero_segment.phases["P4"].obj == 96

    # Guerin's own continuation -- previously overwritten by the bug.
    assert outer.phases["P2"].obj == 105
    assert outer.phases["P3"].action == ActionCode.CAST
    assert outer.phases["P4"].obj == 106


def test_ak3_t9_leader72_triple_nested_plan() -> None:
    # A Cast (P0) embeds a nested plan whose own P1 is a Hire that embeds
    # a further nested plan -- confirms the fix recurses correctly to at
    # least 3 levels deep on real data.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T9.K1")
    teleko = next(leader for leader in kingdom.leaders if leader.leader_id == 72)
    level0 = teleko.plan.segments[0]

    p0 = level0.phases["P0"]
    assert p0.action == ActionCode.CAST
    assert p0.nested_plan is not None
    assert p0.nested_plan.leader_id == 13  # Cast(Resurrection, target=13)'s target IS the resurrected character's id

    level1 = p0.nested_plan.segments[0]
    assert (level1.plan_start, level1.plan_end) == (1, 4)
    p1 = level1.phases["P1"]
    assert p1.action == ActionCode.HIRE
    assert p1.obj == 34
    assert p1.nested_plan is not None
    assert p1.nested_plan.leader_id == 34

    level2 = p1.nested_plan.segments[0]
    assert (level2.plan_start, level2.plan_end) == (2, 4)
    assert set(level2.phases) == {"P2", "P3", "P4"}

    # Level 1's own continuation (P2-P4), recovered correctly.
    assert level1.phases["P2"].action == ActionCode.RECRUIT
    assert level1.phases["P4"].action == ActionCode.LEAVE

    # Level 0 (Teleko)'s own continuation (P1-P4), recovered correctly.
    assert level0.phases["P1"].action == ActionCode.CAST
    assert level0.phases["P1"].nested_plan is None  # this Cast triggers no further nesting
    assert level0.phases["P4"].obj == 10


@pytest.mark.parametrize("path", ALL_MOVE_FILES, ids=lambda p: p.name)
def test_every_leader_has_exactly_one_top_level_segment(path: Path) -> None:
    # Empirical finding from fixing the nested-plan bug: none of the 10
    # sample files has a genuine sibling AP: segment for any leader --
    # every extra AP: block previously counted as a "second segment" was
    # actually a nested Hire/Cast plan, now correctly attached to the
    # triggering phase instead of `leader.plan.segments`.
    kingdom = parse_k1_moves_file(path)
    for leader in kingdom.leaders:
        assert len(leader.plan.segments) == 1, f"leader {leader.leader_id} in {path.name}"


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
