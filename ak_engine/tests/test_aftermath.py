from __future__ import annotations

import random

import pytest

from ak_engine.turn.aftermath import (
    FORMATION_DIVISOR,
    base_quality_change_percent,
    decline_chance,
    improve_chance,
    quality_gain_merit_multiplier,
    roll_quality_change,
)
from ak_engine.turn.combat import Quality


def test_improve_chance_decreases_as_quality_rises():
    assert improve_chance(Quality.DEPLETED) > improve_chance(Quality.VETERAN)
    assert improve_chance(Quality.ELITE) == 0.0


def test_decline_chance_decreases_as_quality_rises():
    assert decline_chance(Quality.GREEN) > decline_chance(Quality.CRACK)
    assert decline_chance(Quality.DEPLETED) == 0.0


def test_winner_improves_when_roll_succeeds():
    rng = random.Random()
    rng.random = lambda: 0.0
    assert roll_quality_change(Quality.AVERAGE, rng, is_winner=True) == Quality.VETERAN


def test_winner_stays_same_when_roll_fails():
    rng = random.Random()
    rng.random = lambda: 0.99
    assert roll_quality_change(Quality.AVERAGE, rng, is_winner=True) == Quality.AVERAGE


def test_winner_cannot_exceed_elite():
    rng = random.Random()
    rng.random = lambda: 0.0
    assert roll_quality_change(Quality.ELITE, rng, is_winner=True) == Quality.ELITE


def test_druid_led_green_unit_has_reduced_improve_chance():
    # Phase 372: improve_chance(GREEN, front) = base_quality_change_percent
    # (GREEN=1, divisor=1) = 60 >> max(0,1+1-2) = 60 >> 0 = 0.60; druid-led
    # multiplier for GREEN is 0.60 -> 0.36. A roll of 0.5 clears the
    # unmodified chance but not the druid-led one.
    rng = random.Random()
    rng.random = lambda: 0.5

    unmodified = roll_quality_change(Quality.GREEN, rng, is_winner=True)
    druid_led = roll_quality_change(Quality.GREEN, rng, is_winner=True, led_by_insufficient_druid=True)

    assert unmodified == Quality.AVERAGE
    assert druid_led == Quality.GREEN


def test_loser_that_retreated_may_decline():
    rng = random.Random()
    rng.random = lambda: 0.0
    assert roll_quality_change(Quality.AVERAGE, rng, is_winner=False, retreated=True) == Quality.GREEN


def test_loser_that_retreated_cannot_go_below_depleted():
    rng = random.Random()
    rng.random = lambda: 0.0
    assert roll_quality_change(Quality.DEPLETED, rng, is_winner=False, retreated=True) == Quality.DEPLETED


def test_loser_that_did_not_retreat_can_improve_or_decline():
    rng = random.Random()

    rng.random = lambda: 0.0
    declined = roll_quality_change(Quality.AVERAGE, rng, is_winner=False, retreated=False)
    assert declined == Quality.GREEN

    rng.random = lambda: 0.99
    unchanged = roll_quality_change(Quality.AVERAGE, rng, is_winner=False, retreated=False)
    assert unchanged == Quality.AVERAGE


# -- Phase 350: the confirmed AK.EXE/AK.OVR quality-change formula --------


def test_base_quality_change_percent_matches_the_source_table():
    # Source: base_percent_table, one row per formation depth, indexed
    # by Quality's own 0-5 ordinal (Depleted..Elite).
    table = {
        "front": [0.60, 0.60, 0.30, 0.15, 0.07, 0.03],
        "second": [0.60, 0.30, 0.15, 0.07, 0.03, 0.01],
        "third": [0.15, 0.07, 0.03, 0.01, 0.0, 0.0],
        "fourth_and_later": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    for depth, expected_row in table.items():
        divisor = FORMATION_DIVISOR[depth]
        for quality, expected in zip(Quality, expected_row):
            assert base_quality_change_percent(quality, divisor) == pytest.approx(expected), (depth, quality)


def test_quality_gain_merit_multiplier_matches_the_source_table():
    assert quality_gain_merit_multiplier(0) == 1.0
    assert quality_gain_merit_multiplier(5) == 1.0
    assert quality_gain_merit_multiplier(-1) == 0.6
    assert quality_gain_merit_multiplier(-2) == 0.2
    assert quality_gain_merit_multiplier(-3) == 0.0
    assert quality_gain_merit_multiplier(-10) == 0.0


# -- Phase 372: the real formula wired into improve_chance/decline_chance/
# roll_quality_change ------------------------------------------------------


def test_decline_chance_uses_the_real_formula_by_formation_depth():
    # AVERAGE (ordinal 2): front 60>>1=30%, second 60>>2=15%, third
    # 60>>4=3%, fourth_and_later 60>>8=0%.
    assert decline_chance(Quality.AVERAGE, FORMATION_DIVISOR["front"]) == pytest.approx(0.30)
    assert decline_chance(Quality.AVERAGE, FORMATION_DIVISOR["second"]) == pytest.approx(0.15)
    assert decline_chance(Quality.AVERAGE, FORMATION_DIVISOR["third"]) == pytest.approx(0.03)
    assert decline_chance(Quality.AVERAGE, FORMATION_DIVISOR["fourth_and_later"]) == 0.0


def test_decline_chance_defaults_to_front_line():
    assert decline_chance(Quality.AVERAGE) == decline_chance(Quality.AVERAGE, FORMATION_DIVISOR["front"])


def test_improve_chance_scales_by_the_real_merit_multiplier():
    # AVERAGE front base is 30% -- score>=0 keeps it, -1/-2 scale it down
    # by the source's own gain_merit_multiplier, -3-or-worse zeroes it.
    front = FORMATION_DIVISOR["front"]
    assert improve_chance(Quality.AVERAGE, front, score=0) == pytest.approx(0.30)
    assert improve_chance(Quality.AVERAGE, front, score=-1) == pytest.approx(0.18)
    assert improve_chance(Quality.AVERAGE, front, score=-2) == pytest.approx(0.06)
    assert improve_chance(Quality.AVERAGE, front, score=-3) == 0.0


def test_improve_chance_stays_zero_at_elite_regardless_of_score():
    assert improve_chance(Quality.ELITE, FORMATION_DIVISOR["front"], score=5) == 0.0


def test_roll_quality_change_threads_formation_divisor_into_the_winner_roll():
    # AVERAGE front improve chance is 30%; second-line is 15% -- a roll of
    # 0.20 clears the front-line chance but not the second-line one.
    rng = random.Random()
    rng.random = lambda: 0.20

    front = roll_quality_change(Quality.AVERAGE, rng, is_winner=True, formation_divisor=FORMATION_DIVISOR["front"])
    second = roll_quality_change(Quality.AVERAGE, rng, is_winner=True, formation_divisor=FORMATION_DIVISOR["second"])

    assert front == Quality.VETERAN
    assert second == Quality.AVERAGE


def test_roll_quality_change_threads_score_into_the_winner_roll():
    # AVERAGE front improve chance is 30% at score=0, 6% at score=-2 --
    # a roll of 0.10 clears the first but not the second.
    rng = random.Random()
    rng.random = lambda: 0.10

    neutral_score = roll_quality_change(Quality.AVERAGE, rng, is_winner=True, score=0)
    low_score = roll_quality_change(Quality.AVERAGE, rng, is_winner=True, score=-2)

    assert neutral_score == Quality.VETERAN
    assert low_score == Quality.AVERAGE
