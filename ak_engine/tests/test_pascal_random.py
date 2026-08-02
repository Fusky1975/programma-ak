from __future__ import annotations

from ak_engine.worldgen.pascal_random import IRAND_RANGE, MODULUS, MULTIPLIER, PascalRandom


def test_multiplier_is_the_real_borland_constant_0x8088405():
    # Source: 134775813 == 0x8088405, the historically documented
    # Turbo Pascal RandSeed multiplier -- not a value this project chose.
    assert MULTIPLIER == 0x8088405


def test_state_transition_matches_the_confirmed_formula():
    rng = PascalRandom(seed=1)
    expected_next_state = (1 * MULTIPLIER + 1) % MODULUS
    rng.random()
    assert rng.state == expected_next_state


def test_same_seed_produces_identical_sequences():
    a = PascalRandom(seed=12345)
    b = PascalRandom(seed=12345)
    sequence_a = [a.irand() for _ in range(50)]
    sequence_b = [b.irand() for _ in range(50)]
    assert sequence_a == sequence_b


def test_different_seeds_diverge():
    a = PascalRandom(seed=1)
    b = PascalRandom(seed=2)
    assert [a.irand() for _ in range(20)] != [b.irand() for _ in range(20)]


def test_seed_is_reduced_modulo_2_32():
    a = PascalRandom(seed=5)
    b = PascalRandom(seed=5 + MODULUS)
    assert a.irand() == b.irand()


def test_random_stays_within_0_1():
    rng = PascalRandom(seed=42)
    for _ in range(5000):
        value = rng.random()
        assert 0.0 <= value < 1.0


def test_irand_stays_within_documented_range():
    rng = PascalRandom(seed=7)
    for _ in range(5000):
        value = rng.irand()
        assert 0 <= value < IRAND_RANGE


def test_irand_distribution_is_roughly_uniform_over_a_large_sample():
    rng = PascalRandom(seed=999)
    n = 200_000
    total = sum(rng.irand() for _ in range(n))
    mean = total / n
    expected_mean = (IRAND_RANGE - 1) / 2
    assert abs(mean - expected_mean) < expected_mean * 0.02


def test_each_call_both_advances_and_consumes_the_state():
    rng = PascalRandom(seed=1)
    state_before = rng.state
    rng.irand()
    assert rng.state != state_before
