from __future__ import annotations

from ak_engine.models.enums import ActionCode
from ak_engine.models.map import Terrain
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.use_mi_decode import UseMIRequest, decode_use_mi_phase


def test_decode_use_mi_phase_passes_item_instance_id_and_target_through():
    # No real Use_MI phase exists in any sample AK3__T*.K1 file (see
    # module docstring) -- this is a synthetic value only.
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=31, extra=[97])

    request = decode_use_mi_phase(phase)

    assert request.item_instance_id == 31
    assert request.target == 97
    assert request.terrain is None


def test_decode_use_mi_phase_handles_empty_extra():
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=5, extra=[])

    request = decode_use_mi_phase(phase)

    assert request.item_instance_id == 5
    assert request.target == 0
    assert request.terrain is None


def test_decode_use_mi_phase_reads_a_second_extra_element_as_terrain():
    # Structurally mirrors Cast's Illus_Terrain sub-read (same Read_More
    # mechanism, per DEF2.PAS) -- synthetic, since no real example exists.
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=34, extra=[142, 3])

    request = decode_use_mi_phase(phase)

    assert request.item_instance_id == 34
    assert request.target == 142
    assert request.terrain == Terrain.FOREST


def test_decode_use_mi_phase_keeps_out_of_range_terrain_raw():
    phase = PlanPhase(label="P0", action=ActionCode.USE_MI, obj=34, extra=[142, 99])

    request = decode_use_mi_phase(phase)

    assert request.terrain == 99


def test_use_mi_request_is_a_plain_dataclass():
    request = UseMIRequest(item_instance_id=1, target=2, terrain=None)
    assert request.item_instance_id == 1
    assert request.target == 2
