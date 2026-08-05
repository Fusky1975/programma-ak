from __future__ import annotations

from ak_engine.models.enums import ActionCode, Spell
from ak_engine.models.plan import PlanPhase
from ak_engine.turn.trade_decode import TradeRequest, decode_trade_phase, rewrite_trade_as_secret_spell_cast


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


# -- rewrite_trade_as_secret_spell_cast (Phase 397, DEF2.PAS R_HPlan's Trade branch) --


def test_rewrite_trade_as_secret_spell_cast_self_targeted_gate_angel():
    # "GI 25 to #1" from leader 1 to themself -- tl == sldr, obj in [25,34].
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[1, 3])

    request = rewrite_trade_as_secret_spell_cast(phase, leader_id=1)

    assert request is not None
    assert request.spell == Spell.GATE_ANGEL
    assert request.target == 0  # lextra[m] := 0, per DEF2.PAS -- always zeroed, even here


def test_rewrite_trade_as_secret_spell_cast_covers_every_secret_spell_ordinal():
    for ordinal in range(25, 35):
        phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=ordinal, extra=[9])
        request = rewrite_trade_as_secret_spell_cast(phase, leader_id=9)
        assert request is not None
        assert request.spell == Spell(ordinal)


def test_rewrite_trade_as_secret_spell_cast_none_when_not_self_targeted():
    # An ordinary Give to a different, co-located leader -- tl != sldr.
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[0, 3])

    assert rewrite_trade_as_secret_spell_cast(phase, leader_id=1) is None


def test_rewrite_trade_as_secret_spell_cast_none_for_ordinary_item_or_gold_obj():
    # obj below the secret-spell range -- an ordinary self-Give (unusual but not a rewrite trigger).
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=24, extra=[1])

    assert rewrite_trade_as_secret_spell_cast(phase, leader_id=1) is None


def test_rewrite_trade_as_secret_spell_cast_none_above_secret_spell_range():
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=35, extra=[1])

    assert rewrite_trade_as_secret_spell_cast(phase, leader_id=1) is None


def test_rewrite_trade_as_secret_spell_cast_none_for_empty_extra():
    phase = PlanPhase(label="P1", action=ActionCode.TRADE, obj=int(Spell.GATE_ANGEL), extra=[])

    assert rewrite_trade_as_secret_spell_cast(phase, leader_id=1) is None
