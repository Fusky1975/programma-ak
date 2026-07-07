from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.recruit_decode import decode_recruit_phase


def phase(obj: int, extra: list[int]) -> PlanPhase:
    return PlanPhase(label="P0", action=ActionCode.RECRUIT, obj=obj, extra=extra)


def test_decodes_noleader_sentinel():
    request = decode_recruit_phase(phase(255, [0, 0, -1]))
    assert request.leader_id is None
    assert request.army_types == [ArmyType.GARRISON]


def test_decodes_real_leader_id():
    request = decode_recruit_phase(phase(72, [0, 1, 1, 10, -1]))
    assert request.leader_id == 72
    assert request.army_types == [ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.WARG_RIDERS]


def test_decodes_multiple_army_types_real_example():
    # ('AK3__T4.K1', 32, 'P0', 32, [0, 14, 2, 0, -1]) from AK3__T4.K1
    request = decode_recruit_phase(phase(32, [0, 14, 2, 0, -1]))
    assert request.leader_id == 32
    assert request.army_types == [ArmyType.FLEET, ArmyType.AXEMEN, ArmyType.GARRISON]


def test_real_examples_from_ak3_files_all_decode_cleanly():
    real_examples = [
        (1, [0, 1, 1, 10, -1], [ArmyType.BOWMEN, ArmyType.BOWMEN, ArmyType.WARG_RIDERS]),
        (255, [0, 0, -1], [ArmyType.GARRISON]),
        (18, [0, 11, -1], [ArmyType.DRAGON_WING]),
        (18, [0, 12, -1], [ArmyType.EAGLE_WING]),
        (72, [0, 1, 1, -1], [ArmyType.BOWMEN, ArmyType.BOWMEN]),
        (1, [0, 11, -1], [ArmyType.DRAGON_WING]),
        (97, [0, 0, 0, -1], [ArmyType.GARRISON, ArmyType.GARRISON]),
        (97, [0, 18, -1], [ArmyType.TROLLS]),
    ]
    for obj, extra, expected_types in real_examples:
        request = decode_recruit_phase(phase(obj, extra))
        assert request.army_types == expected_types
        assert request.unmapped_ordinals == []


def test_unmapped_ordinal_is_reported_not_silently_dropped():
    request = decode_recruit_phase(phase(255, [0, 15, 99, -1]))
    assert request.army_types == []
    assert request.unmapped_ordinals == [15, 99]


def test_handles_extra_without_trailing_sentinel():
    request = decode_recruit_phase(phase(255, [0, 1]))
    assert request.army_types == [ArmyType.BOWMEN]
