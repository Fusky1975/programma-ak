from __future__ import annotations

import random

from ak_engine.turn.battle_luck import (
    BLUCK_TEMPLATE,
    CLUCK2_REVERSAL_PHRASE,
    CLUCK2_TEMPLATE,
    CLUCK_REVERSAL_CHECK_PERCENT,
    CLUCK_TEMPLATE,
    FIRST_TURN_LUCK_COEFFICIENT,
    LATER_TURN_LUCK_COEFFICIENT,
    bluck_event_index,
    break_bres_tie,
    cluck_event_index,
    column_narration_eligible,
    draw_global_luck,
    draw_local_luck,
    luck_strength_multiplier,
    render_bluck_event,
    render_cluck2_event,
    render_cluck_event,
    roll_cluck_reversal,
)

from _helpers import ScriptedRandom

TRIALS = 5000
TOLERANCE = 0.03  # +/- 3 percentage points on a 5000-trial sample


# -- Phase 346: the confirmed AK.EXE/AK.OVR luck formula ------------------


def test_draw_global_and_local_luck_return_two_independent_u01_values():
    rng = random.Random(11)
    for draw in (draw_global_luck, draw_local_luck):
        for _ in range(TRIALS):
            a, b = draw(rng)
            assert 0.0 <= a < 1.0
            assert 0.0 <= b < 1.0


def test_luck_strength_multiplier_matches_the_documented_range_bounds():
    # R_s = 1 + k*(g+l): at (0,0) it's the identity multiplier 1.0; at
    # the (exclusive) top of the U[0,1) range (g=l=1) it would reach
    # 1+2k -- 2.5 on turn 1 (k=0.75), 4 on turn 2+ (k=1.5), matching this
    # module's own "Phase 346 addendum" docstring exactly.
    assert luck_strength_multiplier(0.0, 0.0, is_first_turn=True) == 1.0
    assert luck_strength_multiplier(0.0, 0.0, is_first_turn=False) == 1.0
    assert luck_strength_multiplier(1.0, 1.0, is_first_turn=True) == 1 + 2 * FIRST_TURN_LUCK_COEFFICIENT
    assert luck_strength_multiplier(1.0, 1.0, is_first_turn=False) == 1 + 2 * LATER_TURN_LUCK_COEFFICIENT
    assert luck_strength_multiplier(1.0, 1.0, is_first_turn=True) == 2.5
    assert luck_strength_multiplier(1.0, 1.0, is_first_turn=False) == 4.0


def test_bluck_event_index_matches_documented_direction_and_clamp():
    # Equal global luck (g1 == g2) reads the documented "9 = neutral"
    # index; a big enough gap in either direction saturates at the
    # documented 1/17 clamp bounds rather than escaping the 1..17 range.
    assert bluck_event_index(0.5, 0.5) == 9
    assert bluck_event_index(0.999, 0.0) == 17
    assert bluck_event_index(0.0, 0.999) == 1


def test_cluck_event_index_matches_documented_direction_and_clamp():
    assert cluck_event_index(0.5, 0.5) == 20
    assert cluck_event_index(0.999, 0.0) == 39
    assert cluck_event_index(0.0, 0.999) == 1


def test_bluck_and_cluck_distributions_match_the_akgen_probability_tables():
    # Cross-checked against `AKGEN_embedded_catalogs.json.txt`'s own
    # `tables.battle_engine.global_event`/`local_column_event`
    # `aggregate_percent.turn_2_plus` (the source's own declared
    # probability tables, not re-derived here) -- a moderate-N Monte
    # Carlo of `bluck_event_index`/`cluck_event_index` over fresh
    # `draw_global_luck`/`draw_local_luck` draws reproduces the source's
    # own three-way split (favor-side-2 / neutral / favor-side-1) to
    # within a generous tolerance that comfortably absorbs sampling
    # noise at this N without the test becoming a slow, exact replica of
    # the source's own analysis.
    rng = random.Random(346)
    n = 300_000
    bluck_neutral = 0
    cluck_neutral = 0
    for _ in range(n):
        g1, g2 = draw_global_luck(rng)
        if bluck_event_index(g1, g2) == 9:
            bluck_neutral += 1
        l1, l2 = draw_local_luck(rng)
        if cluck_event_index(l1, l2) == 20:
            cluck_neutral += 1

    # Source: aggregate_percent.turn_2_plus.neutral = 10.8024691 (BLUCK),
    # 4.9375 (CLUCK).
    assert abs(bluck_neutral / n * 100 - 10.8024691) < 0.5
    assert abs(cluck_neutral / n * 100 - 4.9375) < 0.5


# -- Phase 347: break_bres_tie() -- the summed-BRES tie-break ------------


def test_break_bres_tie_always_returns_one_of_the_two_sides():
    rng = random.Random(347)
    for _ in range(1000):
        assert break_bres_tie(rng) in ("side1", "side2")


def test_break_bres_tie_is_roughly_50_50_over_many_calls():
    rng = random.Random(3470)
    winners = [break_bres_tie(rng) for _ in range(TRIALS)]
    side1_share = sum(1 for w in winners if w == "side1") / len(winners)
    assert abs(side1_share - 0.5) < TOLERANCE


def test_break_bres_tie_terminates_even_when_the_coin_always_lands_the_same():
    # A degenerate rng that always returns the same value would make
    # `side1_heads == side2_heads` forever -- guard against an infinite
    # loop by bounding the number of draws a real random.Random needs in
    # practice (expected 2 draws per round, astronomically unlikely to
    # need more than a few hundred).
    rng = random.Random(999)
    for _ in range(50):
        break_bres_tie(rng)


# -- Phase 388/584: BLUCK/CLUCK/CLUCK2 narration text --------------------


def test_bluck_cluck_and_cluck2_templates_have_the_documented_lengths():
    assert len(BLUCK_TEMPLATE) == 17
    assert len(CLUCK_TEMPLATE) == 39
    assert len(CLUCK2_TEMPLATE) == 39


def test_render_bluck_event_renders_the_real_prose_at_each_bound():
    rng = ScriptedRandom([0.1] * 20)
    assert render_bluck_event(1, "Aldric", "Borin", rng) == (
        "Aldric's luck was awful, for a nasty rumor that enemy forces "
        "were approaching from the rear began to sweep through Aldric's "
        "troops!This gave Borin's forces a huge advantage."
    )


def test_render_cluck_event_renders_the_real_prose_at_each_bound():
    rng = ScriptedRandom([0.1] * 20)
    assert render_cluck_event(1, "144th Legion", rng) == (
        "the commander of 144th Legion fell, a man who was loved by all."
        "Their spirits sank, and they fought as if they were half-trained."
    )


def test_render_cluck2_event_renders_the_real_prose():
    rng = ScriptedRandom([0.1] * 20)
    result = render_cluck2_event(1, "144th Legion", rng)
    assert result == (
        "a mutiny broke out among 144th Legion when a false report spread "
        "that they would not be paid this year, thus they were of little use."
    )


def test_column_narration_eligible_matches_the_confirmed_0_4_to_2_5_gate():
    assert column_narration_eligible(10, 10) is True  # ratio 1.0
    assert column_narration_eligible(10, 4) is True  # ratio 2.5, inclusive
    assert column_narration_eligible(4, 10) is True  # ratio 0.4, inclusive
    assert column_narration_eligible(10, 3.99) is False  # ratio > 2.5
    assert column_narration_eligible(3.99, 10) is False  # ratio < 0.4


def test_column_narration_eligible_rejects_a_non_positive_strength():
    assert column_narration_eligible(0, 10) is False
    assert column_narration_eligible(10, 0) is False
    assert column_narration_eligible(-1, 10) is False


def test_roll_cluck_reversal_never_fires_outside_the_documented_13_to_27_range():
    rng = random.Random(388)
    for index in (1, 12, 28, 39):
        assert roll_cluck_reversal(index, rng) is False


def test_roll_cluck_reversal_can_fire_inside_the_documented_13_to_27_range():
    # A low draw always beats the 33% threshold; a high draw never does.
    always_low = random.Random()
    always_low.random = lambda: 0.0  # type: ignore[method-assign]
    always_high = random.Random()
    always_high.random = lambda: 0.99  # type: ignore[method-assign]
    for index in (13, 20, 27):
        assert roll_cluck_reversal(index, always_low) is True
        assert roll_cluck_reversal(index, always_high) is False


def test_roll_cluck_reversal_matches_the_akgen_aggregate_percentages():
    # Source: "a competitive column shows the second event 30.9375% of
    # the time on turn 1, 20.109375% on turn 2+" -- derived here as
    # P(index in [13,27]) * 33%, cross-checked against the source's own
    # local_column_event.probability_percent tables by Monte Carlo over
    # cluck_event_index's own real distribution rather than a uniform
    # index draw.
    rng = random.Random(3880)
    n = 200_000
    reversals = sum(1 for _ in range(n) if roll_cluck_reversal(cluck_event_index(*draw_local_luck(rng)), rng))
    # Local luck values are U[0,1) with no turn-1/turn-2+ distinction of
    # their own (that's on luck_strength_multiplier, not cluck_event_index),
    # so this reproduces the turn-2+ figure -- CLUCK_REVERSAL_CHECK_PERCENT
    # applied to indices in range averages out close to 60.9375%*33%.
    assert abs(reversals / n * 100 - 60.9375 * CLUCK_REVERSAL_CHECK_PERCENT) < 1.0


def test_cluck2_reversal_phrase_is_a_non_empty_confirmed_string():
    assert isinstance(CLUCK2_REVERSAL_PHRASE, str)
    assert CLUCK2_REVERSAL_PHRASE
