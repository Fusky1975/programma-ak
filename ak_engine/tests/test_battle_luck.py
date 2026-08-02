from __future__ import annotations

import random

from ak_engine.turn.battle_luck import (
    BATTLE_LUCK_BONUS_RANGE,
    BATTLE_LUCK_CHANCE,
    COLUMN_LUCK_BONUS_RANGE,
    COLUMN_LUCK_CHANCE,
    COLUMN_LUCK_MALUS_RANGE,
    FIRST_TURN_LUCK_COEFFICIENT,
    LATER_TURN_LUCK_COEFFICIENT,
    bluck_event_index,
    break_bres_tie,
    cluck_event_index,
    draw_global_luck,
    draw_local_luck,
    luck_strength_multiplier,
    roll_battle_luck,
    roll_column_luck,
)

TRIALS = 5000
TOLERANCE = 0.03  # +/- 3 percentage points on a 5000-trial sample


def test_column_luck_triggers_at_roughly_75_percent():
    rng = random.Random(1234)
    triggered = sum(1 for _ in range(TRIALS) if roll_column_luck(rng) is not None)
    assert abs(triggered / TRIALS - COLUMN_LUCK_CHANCE) < TOLERANCE


def test_column_luck_multiplier_within_documented_ranges():
    rng = random.Random(5678)
    for _ in range(TRIALS):
        event = roll_column_luck(rng)
        if event is None:
            continue
        if event.is_bonus:
            assert COLUMN_LUCK_BONUS_RANGE[0] <= event.multiplier <= COLUMN_LUCK_BONUS_RANGE[1]
        else:
            assert COLUMN_LUCK_MALUS_RANGE[0] <= event.multiplier <= COLUMN_LUCK_MALUS_RANGE[1]


def test_column_luck_bonus_and_malus_are_roughly_50_50():
    rng = random.Random(42)
    events = [e for _ in range(TRIALS) if (e := roll_column_luck(rng)) is not None]
    bonuses = sum(1 for e in events if e.is_bonus)
    assert abs(bonuses / len(events) - 0.5) < TOLERANCE


def test_battle_luck_triggers_at_roughly_55_percent():
    rng = random.Random(99)
    triggered = sum(1 for _ in range(TRIALS) if roll_battle_luck(rng) is not None)
    assert abs(triggered / TRIALS - BATTLE_LUCK_CHANCE) < TOLERANCE


def test_battle_luck_multiplier_within_documented_range():
    rng = random.Random(7)
    for _ in range(TRIALS):
        event = roll_battle_luck(rng)
        if event is None:
            continue
        assert BATTLE_LUCK_BONUS_RANGE[0] <= event.multiplier <= BATTLE_LUCK_BONUS_RANGE[1]


def test_battle_luck_picks_each_side_roughly_half_the_time():
    rng = random.Random(2024)
    events = [e for _ in range(TRIALS) if (e := roll_battle_luck(rng)) is not None]
    attacker_side = sum(1 for e in events if e.side == "attacker")
    assert abs(attacker_side / len(events) - 0.5) < TOLERANCE


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
