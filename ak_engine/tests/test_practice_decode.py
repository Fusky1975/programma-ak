from __future__ import annotations

from collections import Counter
from pathlib import Path

from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.practice_decode import PracticeRequest, decode_practice_phase

GAME_DATA_DIR = Path(__file__).resolve().parents[2]


def _walk_phases(plan):
    for segment in plan.segments:
        for label, phase in segment.phases.items():
            yield label, phase
            if phase.nested_plan is not None:
                yield from _walk_phases(phase.nested_plan)


def test_decode_practice_phase_maps_obj_to_ability():
    phase = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=14, extra=[0])

    request = decode_practice_phase(phase)

    assert request == PracticeRequest(ability=Ability.SAGE)


def test_decode_practice_phase_keeps_out_of_range_obj_raw():
    phase = PlanPhase(label="P0", action=ActionCode.PRACTICE, obj=99, extra=[0])

    request = decode_practice_phase(phase)

    assert request.ability == 99


def test_decode_practice_phase_against_every_real_move_file():
    # Empirical distribution across all 10 sample AK3__T*.K1 files,
    # independently re-verified via the real parser: 189 total real
    # Practice phases, obj always in {1, 2, 5, 6, 14} in this sample
    # (Ability.MARCH, NAVAL, WHITE, NECROMANCY, SAGE), extra always [0].
    expected_counts = {
        Ability.MARCH: 8,
        Ability.NAVAL: 2,
        Ability.WHITE: 8,
        Ability.NECROMANCY: 31,
        Ability.SAGE: 140,
    }

    counts: Counter[Ability] = Counter()
    total = 0
    for n in range(1, 11):
        kingdom = parse_k1_moves_file(GAME_DATA_DIR / f"AK3__T{n}.K1")
        for leader in kingdom.leaders:
            for _label, phase in _walk_phases(leader.plan):
                if phase.action != ActionCode.PRACTICE:
                    continue
                total += 1
                assert phase.extra == [0], (n, leader.leader_id, phase)
                request = decode_practice_phase(phase)
                assert isinstance(request.ability, Ability), (n, leader.leader_id, phase)
                counts[request.ability] += 1

    assert total == 189
    assert counts == expected_counts
