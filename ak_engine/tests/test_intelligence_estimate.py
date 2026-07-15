from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.temper import Temper
from ak_engine.turn.intelligence_estimate import estimate_alignment, estimate_temper


def test_estimate_alignment_perfect_returns_exact_value():
    result = estimate_alignment(Alignment.EVIL, target_id=3, agent_id=2, perfect=True)
    assert result is Alignment.EVIL


def test_estimate_alignment_nudges_up_when_target_odd_agent_even():
    # Real Pascal ordinal: GOOD=1; target odd(3) contributes +1, agent even(2) contributes -0 -> +1 -> DRUID(2)
    result = estimate_alignment(Alignment.GOOD, target_id=3, agent_id=2, perfect=False)
    assert result is Alignment.DRUID


def test_estimate_alignment_nudges_down_when_target_even_agent_odd():
    # Real Pascal ordinal: NEUTRAL=3; target even(4) contributes +0, agent odd(3) contributes -1 -> -1 -> DRUID(2)
    result = estimate_alignment(Alignment.NEUTRAL, target_id=4, agent_id=3, perfect=False)
    assert result is Alignment.DRUID


def test_estimate_alignment_same_parity_is_unchanged():
    result = estimate_alignment(Alignment.NEUTRAL, target_id=4, agent_id=2, perfect=False)
    assert result is Alignment.NEUTRAL


def test_estimate_alignment_clamps_at_top_of_range():
    # SPECIAL is the highest ordinal -- nudging further up must clamp, not wrap or overflow.
    result = estimate_alignment(Alignment.SPECIAL, target_id=3, agent_id=2, perfect=False)
    assert result is Alignment.SPECIAL


def test_estimate_alignment_clamps_at_bottom_of_range():
    # DIVINE is ordinal 0 -- nudging further down must clamp at 0, not go negative.
    result = estimate_alignment(Alignment.DIVINE, target_id=4, agent_id=3, perfect=False)
    assert result is Alignment.DIVINE


def test_estimate_temper_perfect_returns_exact_value():
    result = estimate_temper(Temper.CAUTIOUS, target_id=3, agent_birth_x=2, perfect=True)
    assert result is Temper.CAUTIOUS


def test_estimate_temper_uses_birth_x_parity_not_agent_id():
    # BRAVE=2; target odd(3) contributes +1, agent_birth_x even(2) contributes -0 -> +1 -> BERSERK(3).
    result = estimate_temper(Temper.BRAVE, target_id=3, agent_birth_x=2, perfect=False)
    assert result is Temper.BERSERK


def test_estimate_temper_clamps_at_top_of_range():
    result = estimate_temper(Temper.BERSERK, target_id=3, agent_birth_x=2, perfect=False)
    assert result is Temper.BERSERK


def test_estimate_temper_clamps_at_bottom_of_range():
    result = estimate_temper(Temper.COWARDLY, target_id=4, agent_birth_x=3, perfect=False)
    assert result is Temper.COWARDLY
