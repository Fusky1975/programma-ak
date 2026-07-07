from __future__ import annotations

import random

from ak_engine.turn.aftermath import decline_chance, improve_chance, roll_quality_change
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
    # improve_chance(GREEN) = 0.5*(1-1/5) = 0.4; druid-led multiplier for
    # GREEN is 0.60 -> 0.24. A roll of 0.35 clears the unmodified chance
    # but not the druid-led one.
    rng = random.Random()
    rng.random = lambda: 0.35

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
