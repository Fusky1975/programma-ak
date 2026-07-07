from __future__ import annotations

from ak_engine.models.enums import ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.army_list_decode import decode_army_list_phase


def phase(action: ActionCode, extra: list[int]) -> PlanPhase:
    return PlanPhase(label="P0", action=action, obj=0, extra=extra)


def test_decodes_specific_leader_and_army_ids():
    # Real example: AK3__T1.K1 leader 18's LEAVE -- give armies 108/109/110 to leader 1.
    request = decode_army_list_phase(phase(ActionCode.LEAVE, [1, 108, 109, 110, -1]))
    assert request.target_leader_id == 1
    assert request.army_ids == [108, 109, 110]
    assert request.all_armies is False


def test_decodes_noleader_sentinel_as_none():
    # Real example: AK3__T4.K1 leader 97's LEAVE -- garrison, single army 270.
    request = decode_army_list_phase(phase(ActionCode.LEAVE, [255, 270, -1]))
    assert request.target_leader_id is None
    assert request.army_ids == [270]


def test_lone_255_after_leader_means_all_armies():
    # Real example: AK3__T4.K1 leader 97's LEAVE -- garrison, all armies.
    request = decode_army_list_phase(phase(ActionCode.LEAVE, [255, 255, -1]))
    assert request.target_leader_id is None
    assert request.all_armies is True
    assert request.army_ids == []


def test_real_leave_examples_from_ak3_files_all_decode_cleanly():
    real_examples = [
        ([1, 108, 109, 110, -1], 1, [108, 109, 110], False),
        ([18, 255, -1], 18, [], True),
        ([255, 255, -1], None, [], True),
        ([255, 270, -1], None, [270], False),
        ([49, 53, 267, 70, 155, 83, -1], 49, [53, 267, 70, 155, 83], False),
        ([78, 71, 154, 233, -1], 78, [71, 154, 233], False),
        ([255, 18, -1], None, [18], False),
    ]
    for extra, expected_leader, expected_ids, expected_all in real_examples:
        request = decode_army_list_phase(phase(ActionCode.LEAVE, extra))
        assert request.target_leader_id == expected_leader
        assert request.army_ids == expected_ids
        assert request.all_armies == expected_all


def test_real_disband_example_from_ak3_t9():
    # ('AK3__T9.K1', 22, 'P1', 0, [0, 214, -1])
    request = decode_army_list_phase(phase(ActionCode.DISBAND, [0, 214, -1]))
    assert request.target_leader_id == 0  # not a real leader id for Disband; unused field
    assert request.army_ids == [214]


def test_handles_empty_extra():
    request = decode_army_list_phase(phase(ActionCode.PICK_UP, []))
    assert request.target_leader_id is None
    assert request.army_ids == []
    assert request.all_armies is False
