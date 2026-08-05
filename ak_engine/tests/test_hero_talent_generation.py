from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.worldgen.hero_talent_generation import (
    FAVORED_ALIGNMENT,
    INDEPENDENT_TRAINING_ABILITIES,
    ORDINARY_ALIGNMENT_ROLL,
    primary_increment,
    raw_aptitude_increment,
    roll_alignment,
    roll_aptitude,
    roll_primary_ability,
    roll_skill_and_aptitude_table,
    roll_skill_table,
)
from ak_engine.worldgen.pascal_random import PascalRandom


def test_ordinary_alignment_roll_excludes_divine_and_undead():
    assert Alignment.DIVINE not in ORDINARY_ALIGNMENT_ROLL
    assert Alignment.UNDEAD not in ORDINARY_ALIGNMENT_ROLL
    assert set(ORDINARY_ALIGNMENT_ROLL) == {
        Alignment.GOOD,
        Alignment.DRUID,
        Alignment.NEUTRAL,
        Alignment.PAGAN,
        Alignment.EVIL,
    }


def test_roll_alignment_matches_the_documented_even_20_percent_split():
    rng = PascalRandom(seed=1)
    n = 100_000
    counts = {a: 0 for a in ORDINARY_ALIGNMENT_ROLL}
    for _ in range(n):
        counts[roll_alignment(rng)] += 1
    for alignment in ORDINARY_ALIGNMENT_ROLL:
        assert abs(counts[alignment] / n - 0.20) < 0.01


def test_favored_alignment_covers_all_fifteen_abilities():
    assert set(FAVORED_ALIGNMENT.keys()) == set(Ability)


def test_favored_alignment_never_favored_five():
    for ability in (Ability.TACTICAL, Ability.MARCH, Ability.NAVAL, Ability.ARCHERY, Ability.MELEE):
        assert FAVORED_ALIGNMENT[ability] is None


def test_favored_alignment_matches_the_documented_pairs():
    assert FAVORED_ALIGNMENT[Ability.WHITE] is Alignment.GOOD
    assert FAVORED_ALIGNMENT[Ability.SAGE] is Alignment.GOOD
    assert FAVORED_ALIGNMENT[Ability.DRUID] is Alignment.DRUID
    assert FAVORED_ALIGNMENT[Ability.PSYCHIC] is Alignment.DRUID
    assert FAVORED_ALIGNMENT[Ability.ILLUSION] is Alignment.NEUTRAL
    assert FAVORED_ALIGNMENT[Ability.SPY] is Alignment.NEUTRAL
    assert FAVORED_ALIGNMENT[Ability.ELEMENTAL] is Alignment.PAGAN
    assert FAVORED_ALIGNMENT[Ability.EXPLORER] is Alignment.PAGAN
    assert FAVORED_ALIGNMENT[Ability.NECROMANCY] is Alignment.EVIL
    assert FAVORED_ALIGNMENT[Ability.THIEF] is Alignment.EVIL


def test_primary_increment_forces_druidism_to_exactly_one():
    rng = PascalRandom(seed=2)
    for _ in range(200):
        assert primary_increment(Ability.DRUID, rng) == 1


def test_primary_increment_matches_the_documented_62_5_37_5_split():
    rng = PascalRandom(seed=3)
    n = 50_000
    ones = sum(1 for _ in range(n) if primary_increment(Ability.WHITE, rng) == 1)
    assert abs(ones / n - 0.625) < 0.01


def test_roll_primary_ability_matches_the_three_documented_probability_splits():
    # hero_id 5 -> id_mod16 == Ability.WHITE.value (5); its own probability
    # should be 8/15, every other ability's should be 1/30.
    rng = PascalRandom(seed=4)
    n = 200_000
    counts = {a: 0 for a in Ability}
    for _ in range(n):
        counts[roll_primary_ability(5, rng)] += 1
    assert abs(counts[Ability.WHITE] / n - 8 / 15) < 0.01
    for ability in Ability:
        if ability is not Ability.WHITE:
            assert abs(counts[ability] / n - 1 / 30) < 0.006


def test_roll_primary_ability_id_mod16_15_case_is_uniform():
    # hero_id 15 -> id_mod16 == 15, the out-of-range edge case: uniform 1/15.
    rng = PascalRandom(seed=5)
    n = 200_000
    counts = {a: 0 for a in Ability}
    for _ in range(n):
        counts[roll_primary_ability(15, rng)] += 1
    for ability in Ability:
        assert abs(counts[ability] / n - 1 / 15) < 0.006


def test_raw_aptitude_increment_matches_the_normal_distribution_table():
    # apt_mod=1 ("normal_m1"): 0->48.08%, 1->23.76%, 2->14.58%, 3->8.62%, 4->4.18%, 5+->0.79%
    rng = PascalRandom(seed=6)
    n = 200_000
    buckets = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for _ in range(n):
        value = min(5, raw_aptitude_increment(1, rng))
        buckets[value] += 1
    assert abs(buckets[0] / n - 0.4808) < 0.015
    assert abs(buckets[1] / n - 0.2376) < 0.015
    assert abs((buckets[3] + buckets[4] + buckets[5]) / n - (0.0862 + 0.0418 + 0.0079)) < 0.015


def test_raw_aptitude_increment_matches_the_favored_distribution_table():
    # apt_mod=2 ("favored_m2"): 0->30.12%, 5+->19.99%
    rng = PascalRandom(seed=7)
    n = 200_000
    zero_count = sum(1 for _ in range(n) if raw_aptitude_increment(2, rng) == 0)
    five_plus_count = sum(1 for _ in range(n) if min(5, raw_aptitude_increment(2, rng)) == 5)
    assert abs(zero_count / n - 0.3012) < 0.015
    assert abs(five_plus_count / n - 0.1999) < 0.015


def test_roll_aptitude_never_falls_below_skill_or_exceeds_five():
    rng = PascalRandom(seed=8)
    for _ in range(2000):
        for ability in Ability:
            skill = rng.irand() % 6
            aptitude = roll_aptitude(ability, skill, Alignment.GOOD, rng)
            assert skill <= aptitude <= 5


def test_roll_skill_table_only_touches_the_three_independent_training_abilities_and_one_primary():
    rng = PascalRandom(seed=9)
    for _ in range(500):
        table = roll_skill_table(11, rng)
        nonzero = [a for a in Ability if table.pair_for_ability(a)[0] > 0]
        assert len(nonzero) <= len(INDEPENDENT_TRAINING_ABILITIES) + 1


def test_roll_skill_and_aptitude_table_fills_every_ability():
    rng = PascalRandom(seed=10)
    table = roll_skill_and_aptitude_table(3, Alignment.EVIL, rng)
    for ability in Ability:
        skill, aptitude = table.pair_for_ability(ability)
        assert 0 <= skill <= 9
        assert skill <= aptitude <= 5


def test_roll_skill_and_aptitude_table_is_deterministic_for_a_fixed_seed():
    table_a = roll_skill_and_aptitude_table(3, Alignment.EVIL, PascalRandom(seed=99))
    table_b = roll_skill_and_aptitude_table(3, Alignment.EVIL, PascalRandom(seed=99))
    assert table_a.raw_values == table_b.raw_values
