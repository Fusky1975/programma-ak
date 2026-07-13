from __future__ import annotations

from ak_engine.models.enums import ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.trade_decode import TradeRequest, decode_trade_phase


def test_decode_trade_phase_resolves_target_leader_id_from_extra_1():
    # Phase 133: extra[1] ("n1" in DEF2.PAS) is the co-located recipient's
    # own leader id -- see module docstring for the user-supplied
    # confirmation + DEF2.PAS structural cross-check.
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=3, extra=[0, 77])

    request = decode_trade_phase(phase)

    assert request.obj == 3
    assert request.target_leader_id == 77
    assert request.extra == [0, 77]


def test_decode_trade_phase_handles_empty_extra():
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=5, extra=[])

    request = decode_trade_phase(phase)

    assert request.obj == 5
    assert request.target_leader_id is None
    assert request.extra == []


def test_decode_trade_phase_handles_missing_second_extra_value():
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=5, extra=[0])

    request = decode_trade_phase(phase)

    assert request.target_leader_id is None


def test_decode_trade_phase_does_not_alias_the_phases_extra_list():
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=1, extra=[0, 9])

    request = decode_trade_phase(phase)
    request.extra.append(99)

    assert phase.extra == [0, 9]  # mutating the decoded request must not affect the source phase


def test_trade_request_is_a_plain_dataclass():
    request = TradeRequest(obj=1, target_leader_id=77, extra=[0, 77])
    assert request.obj == 1
    assert request.target_leader_id == 77
    assert request.extra == [0, 77]
