from __future__ import annotations

from ak_engine.models.enums import ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.trail_decode import TrailRequest, decode_trail_phase


def test_decode_trail_phase_reads_target_character():
    # AKMOVES.TXT's own example: (TR)_88_____ / (_Lancelot__), with a
    # blank tactic-list line -- synthetic, since no real Trail phase
    # exists in any sample AK3__T*.K1 file.
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=88, extra=[0])

    request = decode_trail_phase(phase)

    assert request == TrailRequest(target_character_id=88, unconfirmed_extra0=0)


def test_decode_trail_phase_handles_empty_extra():
    phase = PlanPhase(label="P0", action=ActionCode.TRAIL, obj=42, extra=[])

    request = decode_trail_phase(phase)

    assert request.target_character_id == 42
    assert request.unconfirmed_extra0 == 0
