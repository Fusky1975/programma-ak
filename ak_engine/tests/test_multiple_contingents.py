from __future__ import annotations

import random

from ak_engine.models.map import HexCoord
from ak_engine.turn.multiple_contingents import (
    MARCH_UNITE_CHANCE,
    Attacker,
    eligible_to_unite,
    group_attackers_into_battles,
    march_unite_chance,
    roll_unite_for_battle,
)

ORIGIN_A = HexCoord(1, 1)
ORIGIN_B = HexCoord(9, 9)


def test_eligible_to_unite_same_king():
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b = Attacker(leader_id=2, kingdom_id=5, origin_province=ORIGIN_B)
    assert eligible_to_unite(a, b, allied_kingdoms=set())


def test_eligible_to_unite_allied_kings():
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b = Attacker(leader_id=2, kingdom_id=6, origin_province=ORIGIN_B)
    assert eligible_to_unite(a, b, allied_kingdoms={frozenset({5, 6})})


def test_not_eligible_when_unrelated_kingdoms():
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b = Attacker(leader_id=2, kingdom_id=7, origin_province=ORIGIN_B)
    assert not eligible_to_unite(a, b, allied_kingdoms={frozenset({5, 6})})


def test_roll_unite_uses_higher_chance_for_same_origin():
    # March level 0 (the default): 80% at distance 0, 20% at distance 2+
    # (`ORIGIN_A`/`ORIGIN_B` are far more than 2 provinces apart).
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b_same = Attacker(leader_id=2, kingdom_id=5, origin_province=ORIGIN_A)
    b_diff = Attacker(leader_id=3, kingdom_id=5, origin_province=ORIGIN_B)

    rng = random.Random()
    rng.random = lambda: 0.5  # between the two chances (0.20 < 0.5 < 0.80)

    assert roll_unite_for_battle(a, b_same, rng) is True
    assert roll_unite_for_battle(a, b_diff, rng) is False


def test_roll_unite_uses_the_attackers_own_march_level():
    # `a`'s own March level, not the group founder's, drives the chance
    # (module docstring's own Phase 307 reasoning). Proven at distance 2+
    # (`ORIGIN_A`/`ORIGIN_B`), where level 0 is only 20% and level 4 is
    # 60% -- a roll of 0.5 fails the first and succeeds the second.
    a_low_level = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A, march_level=0)
    a_high_level = Attacker(leader_id=2, kingdom_id=5, origin_province=ORIGIN_A, march_level=4)
    b = Attacker(leader_id=3, kingdom_id=5, origin_province=ORIGIN_B)

    rng = random.Random()
    rng.random = lambda: 0.5  # between the two chances (0.20 < 0.5 < 0.60)

    assert roll_unite_for_battle(a_low_level, b, rng) is False
    assert roll_unite_for_battle(a_high_level, b, rng) is True


def test_march_unite_chance_matches_the_march_table():
    # RULES.AK [4.12] MARCH TABLE / Regolamento AK.txt's own "TABELLA
    # DELLA MARCIA" -- transcribed directly, module docstring's own Phase
    # 307 addendum.
    assert MARCH_UNITE_CHANCE == {
        0: (0.80, 0.50, 0.20),
        1: (0.90, 0.60, 0.30),
        2: (1.00, 0.70, 0.40),
        3: (1.00, 0.80, 0.50),
        4: (1.00, 0.90, 0.60),
    }
    for level, (d0, d1, d2) in MARCH_UNITE_CHANCE.items():
        assert march_unite_chance(level, 0) == d0
        assert march_unite_chance(level, 1) == d1
        assert march_unite_chance(level, 2) == d2


def test_march_unite_chance_clamps_beyond_the_tables_own_bounds():
    # Distances past 2 clamp to the distance-2 column; levels past 4
    # clamp to the level-4 row -- no extrapolation beyond sourced data.
    assert march_unite_chance(0, 5) == march_unite_chance(0, 2)
    assert march_unite_chance(9, 0) == march_unite_chance(4, 0)
    assert march_unite_chance(-1, -1) == march_unite_chance(0, 0)


def test_group_attackers_same_king_same_origin_unite():
    attackers = [
        Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A),
        Attacker(leader_id=2, kingdom_id=5, origin_province=ORIGIN_A),
    ]
    rng = random.Random()
    rng.random = lambda: 0.0  # always succeeds

    groups = group_attackers_into_battles(attackers, allied_kingdoms=set(), rng=rng)

    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_group_attackers_unrelated_kingdoms_always_separate():
    attackers = [
        Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A),
        Attacker(leader_id=2, kingdom_id=99, origin_province=ORIGIN_A),
    ]
    rng = random.Random()
    rng.random = lambda: 0.0  # would always succeed if eligible, but they aren't

    groups = group_attackers_into_battles(attackers, allied_kingdoms=set(), rng=rng)

    assert len(groups) == 2
