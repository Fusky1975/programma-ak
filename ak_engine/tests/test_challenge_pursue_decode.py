from __future__ import annotations

from ak_engine.models.enums import ActionCode, Maneuver
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.challenge_pursue_decode import (
    ChallengeRequest,
    PursueRequest,
    decode_challenge_phase,
    decode_pursue_phase,
)
from ak_engine.turn.search_decode import SearchTactic


def test_decode_challenge_phase_reads_target_character_and_tactics():
    # Official move-sheet example shape: (EN)_88_____ / (_Lancelot__) with
    # a tactic list -- synthetic, since no real Challenge phase exists.
    phase = PlanPhase(label="P0", action=ActionCode.CHALLENGE, obj=88, extra=[0, 3, 9, -1])

    request = decode_challenge_phase(phase)

    assert request == ChallengeRequest(
        target_character_id=88,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(Maneuver.TALK), SearchTactic(Maneuver.MELEE)],
    )


def test_decode_pursue_phase_reads_target_character_and_tactics():
    # AKMOVES.TXT's own example: (PU)_88_____ with tactic list "CA-FI,ME".
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=88, extra=[0, 0, 11, 9, -1])

    request = decode_pursue_phase(phase)

    assert request == PursueRequest(
        target_character_id=88,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(Maneuver.CAST, sub_object=11), SearchTactic(Maneuver.MELEE)],
    )


def test_decode_challenge_phase_handles_empty_extra():
    phase = PlanPhase(label="P0", action=ActionCode.CHALLENGE, obj=42, extra=[])

    request = decode_challenge_phase(phase)

    assert request.target_character_id == 42
    assert request.unconfirmed_extra0 == 0
    assert request.tactics == []


def test_decode_pursue_phase_handles_empty_extra():
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=42, extra=[])

    request = decode_pursue_phase(phase)

    assert request.target_character_id == 42
    assert request.unconfirmed_extra0 == 0
    assert request.tactics == []


def test_decode_pursue_phase_targeting_own_character_id_is_not_special_cased():
    # Rulebook [3.16]: targeting yourself becomes a standing "Patrol" --
    # this module deliberately doesn't special-case it, just decodes obj.
    phase = PlanPhase(label="P0", action=ActionCode.PURSUE, obj=1, extra=[0])

    request = decode_pursue_phase(phase)

    assert request.target_character_id == 1
