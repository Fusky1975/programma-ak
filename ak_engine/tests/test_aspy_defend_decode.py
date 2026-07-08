from __future__ import annotations

from ak_engine.models.enums import ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.aspy_defend_decode import (
    DefendRequest,
    SpyProvinceRequest,
    decode_aspy_phase,
    decode_defend_phase,
)


def test_decode_aspy_phase_reads_target_province():
    # AKMOVES.TXT's own example: (SP)_304____ -- synthetic, since no real
    # ASpy phase exists in any sample AK3__T*.K1 file.
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=304, extra=[0])

    request = decode_aspy_phase(phase)

    assert request == SpyProvinceRequest(target_province=304, unconfirmed_extra0=0)


def test_decode_defend_phase_reads_target_province():
    # AKMOVES.TXT's own example: (DE)_304____ -- synthetic, since no real
    # Defend phase exists in any sample AK3__T*.K1 file.
    phase = PlanPhase(label="P0", action=ActionCode.DEFEND, obj=304, extra=[0])

    request = decode_defend_phase(phase)

    assert request == DefendRequest(target_province=304, unconfirmed_extra0=0)


def test_decode_aspy_phase_handles_empty_extra():
    phase = PlanPhase(label="P0", action=ActionCode.ASPY, obj=50, extra=[])

    request = decode_aspy_phase(phase)

    assert request.target_province == 50
    assert request.unconfirmed_extra0 == 0


def test_decode_defend_phase_handles_empty_extra():
    phase = PlanPhase(label="P0", action=ActionCode.DEFEND, obj=50, extra=[])

    request = decode_defend_phase(phase)

    assert request.target_province == 50
    assert request.unconfirmed_extra0 == 0
