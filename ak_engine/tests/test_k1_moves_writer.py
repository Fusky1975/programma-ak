"""Tests for the .K1 move-submission writer -- the inverse of
``parser/k1_moves.py``'s ``parse_k1_moves_file()``. Every real-file test
here is a genuine round trip: parse a real ``AK3__T*.K1`` sample, write
it back out with ``write_k1_moves_file()``, feed the written text
through the real parser again, and assert the re-parsed ``Kingdom``
compares equal to the original (apart from ``source_filename``, which is
derived from whatever path the caller re-parses from, not from file
content) -- not just a shape/format assertion on the writer's own
output. Fixtures come straight from the repo's parent folder (the
original game data), the same convention ``test_k1_moves_parser.py``
already uses.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from ak_engine.models.enums import ActionCode
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader, SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.parser.k1_moves_writer import K1WriteError, write_k1_moves_file

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
ALL_MOVE_FILES = [GAME_DATA_DIR / f"AK3__T{i}.K1" for i in range(1, 11)]


def _round_trip(kingdom: Kingdom) -> Kingdom:
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        return parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)


@pytest.mark.parametrize("path", ALL_MOVE_FILES, ids=lambda p: p.name)
def test_round_trips_every_real_sample_exactly(path: Path) -> None:
    kingdom = parse_k1_moves_file(path)
    reparsed = _round_trip(kingdom)
    assert replace(reparsed, source_filename=kingdom.source_filename) == kingdom


@pytest.mark.parametrize("path", ALL_MOVE_FILES, ids=lambda p: p.name)
def test_round_trip_raises_no_parse_warning(path: Path, recwarn: pytest.WarningsChecker) -> None:
    # A clean round trip shouldn't even trip parse_k1_moves_file()'s own
    # "doesn't look like the expected instructions boilerplate" warning.
    kingdom = parse_k1_moves_file(path)
    _round_trip(kingdom)
    assert len(recwarn) == 0


def _simple_kingdom(*, leaders: list[Leader], king_title: str | None = "Shaman") -> Kingdom:
    return Kingdom(
        source_filename="AK1__T1.K1",
        king_name="Testerman",
        king_title=king_title,
        header=KingdomMoveHeader(raw_fields=[27, 1, 0, 101, 1, 15, 1], sex="M"),
        skills=SkillTable(raw_values=[0] * 30 + [3]),
        leaders=leaders,
    )


def _ordinary_leader(leader_id: int, name: str) -> Leader:
    return Leader(
        leader_id=leader_id,
        name=name,
        plan=ActionPlan(
            leader_id=leader_id,
            segments=[
                PlanSegment(
                    plan_start=0,
                    plan_end=4,
                    sp=(10, -1),
                    phases={
                        "P0": PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=6, extra=[0]),
                        "P1": PlanPhase(label="P1", action=ActionCode.DEFEND, obj=0, extra=[]),
                        "P2": PlanPhase(label="P2", action=ActionCode.WAIT, obj=0, extra=[]),
                        "P3": PlanPhase(label="P3", action=ActionCode.LMOVE, obj=94, extra=[0]),
                        "P4": PlanPhase(label="P4", action=ActionCode.LMOVE, obj=104, extra=[0]),
                    },
                )
            ],
        ),
    )


def test_hand_built_kingdom_round_trips():
    kingdom = _simple_kingdom(leaders=[_ordinary_leader(1, "Testerman")])
    reparsed = _round_trip(kingdom)
    assert replace(reparsed, source_filename=kingdom.source_filename) == kingdom


def test_no_king_title_is_omitted_not_written_as_a_blank_line():
    kingdom = _simple_kingdom(leaders=[_ordinary_leader(1, "Testerman")], king_title=None)
    reparsed = _round_trip(kingdom)
    assert reparsed.king_title is None


def test_nested_hire_plan_round_trips():
    # Hire's own `obj` *is* the newly-joined character's id (rulebook
    # [3.5]) -- confirmed common in real data (9 of the 10 AK3__T*.K1
    # samples use this), not an edge case.
    nested_leader_id = 50
    hiring_leader = Leader(
        leader_id=1,
        name="Testerman",
        plan=ActionPlan(
            leader_id=1,
            segments=[
                PlanSegment(
                    plan_start=0,
                    plan_end=4,
                    sp=(10, -1),
                    phases={
                        "P0": PlanPhase(
                            label="P0",
                            action=ActionCode.HIRE,
                            obj=nested_leader_id,
                            extra=[],
                            nested_plan=ActionPlan(
                                leader_id=nested_leader_id,
                                segments=[
                                    PlanSegment(
                                        plan_start=0,
                                        plan_end=4,
                                        sp=(10, -1),
                                        phases={
                                            "P0": PlanPhase(label="P0", action=ActionCode.DEFEND, obj=0, extra=[]),
                                            "P1": PlanPhase(label="P1", action=ActionCode.DEFEND, obj=0, extra=[]),
                                            "P2": PlanPhase(label="P2", action=ActionCode.DEFEND, obj=0, extra=[]),
                                            "P3": PlanPhase(label="P3", action=ActionCode.DEFEND, obj=0, extra=[]),
                                            "P4": PlanPhase(label="P4", action=ActionCode.DEFEND, obj=0, extra=[]),
                                        },
                                    )
                                ],
                            ),
                        ),
                        "P1": PlanPhase(label="P1", action=ActionCode.DEFEND, obj=0, extra=[]),
                        "P2": PlanPhase(label="P2", action=ActionCode.DEFEND, obj=0, extra=[]),
                        "P3": PlanPhase(label="P3", action=ActionCode.DEFEND, obj=0, extra=[]),
                        "P4": PlanPhase(label="P4", action=ActionCode.DEFEND, obj=0, extra=[]),
                    },
                )
            ],
        ),
    )
    kingdom = _simple_kingdom(leaders=[hiring_leader])
    reparsed = _round_trip(kingdom)
    assert replace(reparsed, source_filename=kingdom.source_filename) == kingdom
    assert reparsed.leaders[0].plan.segments[0].phases["P0"].nested_plan is not None


def test_nested_plan_on_p4_is_rejected():
    # Sourced directly from `parser/k1_moves.py _maybe_parse_nested_plan()`'s
    # own docstring: "only a phase in position P0-P3 can trigger this --
    # P4 never does, which is exactly what disambiguates a nested plan
    # from a genuine new sibling AP: segment for the same leader (only
    # possible right after a P4)." A P4 phase with a nested_plan set
    # would therefore silently misparse as a new sibling segment instead
    # -- this writer refuses to emit that rather than producing a file
    # that wouldn't round-trip.
    nested = ActionPlan(
        leader_id=2,
        segments=[
            PlanSegment(
                0, 4, (10, -1),
                {f"P{n}": PlanPhase(label=f"P{n}", action=ActionCode.DEFEND, obj=0, extra=[]) for n in range(5)},
            )
        ],
    )
    phases = {f"P{n}": PlanPhase(label=f"P{n}", action=ActionCode.DEFEND, obj=0, extra=[]) for n in range(5)}
    phases["P4"] = PlanPhase(label="P4", action=ActionCode.HIRE, obj=2, extra=[], nested_plan=nested)
    leader = Leader(
        leader_id=1,
        name="Testerman",
        plan=ActionPlan(leader_id=1, segments=[PlanSegment(0, 4, (10, -1), phases)]),
    )
    kingdom = _simple_kingdom(leaders=[leader])

    with pytest.raises(K1WriteError):
        write_k1_moves_file(kingdom)


def test_say_tactic_text_is_rejected_not_silently_corrupted():
    # No real AK3__T*.K1 sample contains a SAY tactic (confirmed by
    # tests/test_k1_moves_parser.py's own docstring) -- deliberately
    # unsupported here rather than guessed at (see this writer module's
    # own docstring).
    phases = {f"P{n}": PlanPhase(label=f"P{n}", action=ActionCode.DEFEND, obj=0, extra=[]) for n in range(5)}
    phases["P2"] = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=0, extra=[0, 7, "Hello there"])
    leader = Leader(
        leader_id=1,
        name="Testerman",
        plan=ActionPlan(leader_id=1, segments=[PlanSegment(0, 4, (10, -1), phases)]),
    )
    kingdom = _simple_kingdom(leaders=[leader])

    with pytest.raises(K1WriteError):
        write_k1_moves_file(kingdom)


def test_missing_phase_in_a_segment_is_rejected():
    phases = {f"P{n}": PlanPhase(label=f"P{n}", action=ActionCode.DEFEND, obj=0, extra=[]) for n in range(4)}  # no P4
    leader = Leader(
        leader_id=1,
        name="Testerman",
        plan=ActionPlan(leader_id=1, segments=[PlanSegment(0, 4, (10, -1), phases)]),
    )
    kingdom = _simple_kingdom(leaders=[leader])

    with pytest.raises(K1WriteError):
        write_k1_moves_file(kingdom)
