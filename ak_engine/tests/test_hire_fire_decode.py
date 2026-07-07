from __future__ import annotations

from pathlib import Path

from ak_engine.models.enums import ActionCode
from ak_engine.models.plan import PlanPhase
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.hire_fire_decode import decode_fire_phase, decode_hire_phase

GAME_DATA_DIR = Path(__file__).resolve().parents[2]


def test_decode_hire_phase_reads_hero_id_and_gold_offer():
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[3])

    request = decode_hire_phase(phase)

    assert request.hero_id == 32
    assert request.gold_offer == 3


def test_decode_hire_phase_defaults_gold_offer_when_extra_missing():
    phase = PlanPhase(label="P1", action=ActionCode.HIRE, obj=32, extra=[])

    request = decode_hire_phase(phase)

    assert request.gold_offer == 0


def test_decode_fire_phase_reads_hero_id_only():
    phase = PlanPhase(label="P1", action=ActionCode.FIRE, obj=88, extra=[])

    request = decode_fire_phase(phase)

    assert request.hero_id == 88


def test_decode_hire_phase_against_real_move_file():
    # AK3__T2.K1, leader 18 (Guerin): "P1 : 5 32 3" -> Hire hero 32, offer 3 gold.
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T2.K1")
    leader = next(leader for leader in kingdom.leaders if leader.leader_id == 18)
    hire_phase = leader.plan.segments[0].phases["P1"]
    assert hire_phase.action == ActionCode.HIRE

    request = decode_hire_phase(hire_phase)

    assert request.hero_id == 32
    assert request.gold_offer == 3


def test_decode_hire_phase_gold_offers_are_always_in_rulebook_range_across_real_files():
    # Rulebook [3.5]: "offers a payment of 1-4 gold to the Hero." Every
    # real HIRE phase across all 10 sample files should honor this.
    for n in range(1, 11):
        kingdom = parse_k1_moves_file(GAME_DATA_DIR / f"AK3__T{n}.K1")
        for leader in kingdom.leaders:
            for segment in leader.plan.segments:
                for phase in segment.phases.values():
                    if phase.action == ActionCode.HIRE:
                        request = decode_hire_phase(phase)
                        assert 1 <= request.gold_offer <= 4, (n, leader.leader_id, request)
