from __future__ import annotations

from ak_engine.models.enums import ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.trade_decode import TradeRequest, decode_trade_phase


def test_decode_trade_phase_passes_obj_and_extra_through_unprocessed():
    # No real Trade phase exists in any sample AK3__T*.K1 file (see
    # module docstring) -- this is a synthetic value only, exercising
    # the deliberately-raw pass-through, not a validated real example.
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=42, extra=[7, 3])

    request = decode_trade_phase(phase)

    assert request.obj == 42
    assert request.extra == [7, 3]


def test_decode_trade_phase_handles_empty_extra():
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=5, extra=[])

    request = decode_trade_phase(phase)

    assert request.obj == 5
    assert request.extra == []


def test_decode_trade_phase_does_not_alias_the_phases_extra_list():
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=1, extra=[9])

    request = decode_trade_phase(phase)
    request.extra.append(99)

    assert phase.extra == [9]  # mutating the decoded request must not affect the source phase


def test_trade_request_is_a_plain_dataclass():
    request = TradeRequest(obj=1, extra=[2, 3])
    assert request.obj == 1
    assert request.extra == [2, 3]
