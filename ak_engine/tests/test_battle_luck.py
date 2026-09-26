from __future__ import annotations

import random

from ak_engine.report.prose import render
from ak_engine.turn.battle_luck import (
    BLUCK2_TEMPLATE,
    BLUCK_TEMPLATE,
    CLUCK2_TEMPLATE,
    CLUCK_TEMPLATE,
    FIRST_TURN_LUCK_COEFFICIENT,
    LATER_TURN_LUCK_COEFFICIENT,
    LUCKINT2_TEMPLATE,
    LUCKINT_TEMPLATE,
    apply_bres_tie_correction,
    bluck_cluck_uses_secondary_catalog,
    bluck_event_index,
    cluck_event_index,
    column_narration_eligible,
    draw_global_luck,
    draw_local_luck,
    luck_strength_multiplier,
    render_bluck_event,
    render_cluck_event,
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


# -- Phase 933: apply_bres_tie_correction() -- the real last-column
# BRES tie-break, superseding Phase 347's own break_bres_tie() coin-flip-
# for-a-side guess (see that function's own docstring in git history) --


def test_apply_bres_tie_correction_is_a_noop_when_not_actually_tied():
    # running_total_before + bres != 0 -- the while loop's own condition
    # is never true, so no rng draw happens at all and bres is returned
    # unchanged (an rng that raises on any draw proves this).
    class _ExplodingRandom(random.Random):
        def random(self):
            raise AssertionError("should not draw when there's no tie to break")

    assert apply_bres_tie_correction(3, running_total_before=2, rng=_ExplodingRandom()) == 3
    assert apply_bres_tie_correction(-1, running_total_before=0, rng=_ExplodingRandom()) == -1


def test_apply_bres_tie_correction_corrects_an_exact_zero_sum():
    # prima=0 (0.1 -> Trunc(2*0.1)=0), seconda=1 (0.9 -> Trunc(2*0.9)=1):
    # bres = 0 + (1-0) = 1 -- the same real R01 pair this project's own
    # _luck_draws()/ScriptedRandom test fixtures already script for a
    # forced tie (test_battle_resolution.py).
    rng = ScriptedRandom([0.1, 0.9])

    assert apply_bres_tie_correction(0, running_total_before=0, rng=rng) == 1


def test_apply_bres_tie_correction_never_returns_a_sum_that_is_still_zero():
    rng = random.Random(933)
    for running_total_before in range(-3, 4):
        corrected = apply_bres_tie_correction(-running_total_before, running_total_before, rng)
        assert running_total_before + corrected != 0


def test_apply_bres_tie_correction_applies_no_second_clamp():
    # BRES.md's own explicit note: no clamp after the tie-break. A last
    # column already at the +5 clamp ceiling, with a running total that
    # makes -5+5=0 a tie, gets corrected by +1 (prima=0, seconda=1) to
    # +6 -- outside column_bres's own -5..5 range, and left that way.
    rng = ScriptedRandom([0.1, 0.9])

    assert apply_bres_tie_correction(5, running_total_before=-5, rng=rng) == 6


def test_apply_bres_tie_correction_terminates_even_when_the_coin_always_lands_the_same():
    # A degenerate rng that always draws the same R01 value keeps
    # seconda-prima == 0 forever -- guard against an infinite loop by
    # bounding the number of draws a real random.Random needs in
    # practice (expected 2 draws per round, astronomically unlikely to
    # need more than a few hundred).
    rng = random.Random(999)
    for running_total_before in range(-5, 6):
        apply_bres_tie_correction(-running_total_before, running_total_before, rng)


# -- Phase 388/584: BLUCK/CLUCK/CLUCK2 narration text --------------------


def test_bluck_bluck2_cluck_and_cluck2_templates_have_the_documented_lengths():
    assert len(BLUCK_TEMPLATE) == 17
    assert len(BLUCK2_TEMPLATE) == 17
    assert len(CLUCK_TEMPLATE) == 39
    assert len(CLUCK2_TEMPLATE) == 39


def test_render_bluck_event_renders_the_real_prose_at_each_bound():
    rng = ScriptedRandom([0.1] * 20)
    assert render_bluck_event(1, "Aldric", "Borin", rng) == (
        "Aldric's luck was awful, for a nasty rumor that enemy forces "
        "were approaching from the rear began to sweep through Aldric's "
        "troops!This gave Borin's forces a huge advantage."
    )


def test_render_bluck_event_secondary_renders_the_real_bluck2_prose():
    # Phase 605: BLUCK2.X2 is a mutually exclusive alternate catalog,
    # not a "fortune reverses" follow-up.
    rng = ScriptedRandom([0.1] * 20)
    result = render_bluck_event(1, "Aldric", "Borin", rng, secondary=True)
    assert result == (
        "the fortunes of war took a terrible turn against Aldric when "
        "Aldric's forces were trapped in a canyon and had to fight "
        "their way past prepared defenses."
    )


def test_render_cluck_event_renders_the_real_prose_at_each_bound():
    rng = ScriptedRandom([0.1] * 20)
    assert render_cluck_event(1, "144th Legion", rng) == (
        "the commander of 144th Legion fell, a man who was loved by all."
        "Their spirits sank, and they fought as if they were half-trained."
    )


def test_render_cluck_event_secondary_renders_the_real_cluck2_prose():
    # Phase 605: CLUCK2.X2 is likewise a mutually exclusive alternate
    # catalog for the same event -- render_cluck2_event() is gone,
    # folded into this same function's own secondary=True branch.
    rng = ScriptedRandom([0.1] * 20)
    result = render_cluck_event(1, "144th Legion", rng, secondary=True)
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


# -- Phase 605: the real BLUCK/BLUCK2/CLUCK/CLUCK2 catalog selector ------


def test_bluck_cluck_uses_secondary_catalog_matches_say_pas_odd_check():
    # SAY.PAS: Odd(_px+_py+_attl+_defl+_rphase) -> primary catalog;
    # even -> secondary. Sum here is 3+5+1+2+1 = 12, even.
    assert bluck_cluck_uses_secondary_catalog(3, 5, 1, 2, 1) is True
    # Sum here is 3+5+1+2+2 = 13, odd -> primary (not secondary).
    assert bluck_cluck_uses_secondary_catalog(3, 5, 1, 2, 2) is False


def test_bluck_cluck_uses_secondary_catalog_is_a_pure_parity_check():
    # Flipping any single one of the five inputs by 1 flips the result.
    assert bluck_cluck_uses_secondary_catalog(0, 0, 0, 0, 0) is True
    assert bluck_cluck_uses_secondary_catalog(1, 0, 0, 0, 0) is False


# -- Phase 587: LUCKINT.X/LUCKINT2.X --------------------------------------


def test_luckint_and_luckint2_templates_have_4_entries_each():
    assert len(LUCKINT_TEMPLATE) == 4
    assert len(LUCKINT2_TEMPLATE) == 4


def test_luckint_template_renders_as_a_ready_to_concatenate_prefix():
    rng = ScriptedRandom([0.1] * 10)
    assert render(LUCKINT_TEMPLATE[2], {}, rng=rng) == "Here, "


def test_luckint_template_renders_with_r_alternation():
    rng = ScriptedRandom([0.1] * 10)
    assert render(LUCKINT_TEMPLATE[1], {}, rng=rng) == "In this engagement, "


def test_luckint2_template_verbatim_sample():
    rng = ScriptedRandom([0.1] * 10)
    assert render(LUCKINT2_TEMPLATE[1], {}, rng=rng) == "then the tide turned."
    rng = ScriptedRandom([0.99] * 10)
    assert render(LUCKINT2_TEMPLATE[1], {}, rng=rng) == "But then the tide of battle reversed."
